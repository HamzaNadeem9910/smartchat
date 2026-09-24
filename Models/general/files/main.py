"""
generalBot/main.py
General-Purpose Chatbot — FastAPI Backend  (multi-tenant)

Works for ANY business domain (restaurant, clinic, shop, brand, etc.).
Bot name + knowledge base = auto domain detection.

Multi-tenant: one process now serves EVERY "general" category bot.
bot_id is resolved per-request (URL path, query param, or request body),
falling back to DEFAULT_BOT_ID (env var) only when none is given.
Each bot's config / vector store / system prompt is loaded lazily on
first use and cached in-process.

Run: uvicorn main:app --reload --port 8003
"""

import os, json, re, asyncio, random, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime
from typing import Optional, List

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import openai

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# Config from environment
# ─────────────────────────────────────────────────────────────────

DEFAULT_BOT_ID = int(os.environ.get("BOT_ID", "1"))
_PC_KEY        = os.environ.get("PINECONE_API_KEY", "")
_OAI_KEY       = os.environ.get("OPENAI_API_KEY", "")
_SMARTCHAT_API = os.environ.get("SMARTCHAT_API", "http://127.0.0.1:8000")
SMTP_EMAIL     = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "")

# ─────────────────────────────────────────────────────────────────
# DB helpers  (raw pymysql — same pattern as facultyBot)
# ─────────────────────────────────────────────────────────────────

def _db():
    url = os.environ.get("DATABASE_URL", "mysql+pymysql://root:@127.0.0.1/smartchat_db")
    m = re.match(r"mysql\+pymysql://([^:]*):([^@]*)@([^/:]+)(?::\d+)?/(.+)", url)
    if not m:
        raise RuntimeError(f"Cannot parse DATABASE_URL: {url}")
    user, pw, host, db = m.group(1), m.group(2), m.group(3), m.group(4)
    return pymysql.connect(
        host=host, user=user, password=pw or None,
        database=db, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

def _q1(sql, args=()):
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()

def _qa(sql, args=()):
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()

def _execute(sql, args=()):
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────────
# Load bot config from DB
# ─────────────────────────────────────────────────────────────────

def _load_bot(bot_id: int):
    bot = _q1("""
        SELECT b.id, b.name, b.category, b.subscriber_id,
               s.name  AS org_name,
               s.email AS owner_email,
               COALESCE(s.plan, 'free') AS plan,
               COALESCE(c.header_title,     b.name)                       AS display_name,
               COALESCE(c.welcome_message,  CONCAT('Hi! I am ', b.name, '. How can I help you?')) AS welcome_msg,
               COALESCE(c.theme_color,      '#4285F4')                    AS theme_color,
               COALESCE(c.button_color,     '#34A853')                    AS btn_color,
               COALESCE(c.background_color, '#ffffff')                    AS background_color,
               COALESCE(c.text_color,       '#333333')                    AS text_color,
               COALESCE(c.theme,            'light')                      AS theme,
               COALESCE(c.button_shape,     'rounded')                    AS button_shape,
               COALESCE(c.font_family,      'Inter')                      AS font_family,
               COALESCE(c.font_size,        14)                           AS font_size,
               COALESCE(c.position,         'bottom-right')               AS position,
               COALESCE(c.logo_url,         '')                           AS logo_url
        FROM chatbots b
        JOIN subscribers s ON s.id = b.subscriber_id
        LEFT JOIN chatbot_customization c ON c.chatbot_id = b.id
        WHERE b.id = %s
    """, (bot_id,))
    if not bot:
        raise RuntimeError(f"Bot {bot_id} not found in DB")
    return bot


def _load_faqs(bot_id: int):
    return _qa(
        "SELECT question, answer, category FROM faqs "
        "WHERE chatbot_id = %s AND status = 'active' ORDER BY id",
        (bot_id,)
    )


def _load_pinecone_index(bot_id: int):
    """
    Returns the Pinecone index name for this bot.
    Matches faculty bot pattern: category-based fixed index name.
    'general' category always uses the 'general' index.
    """
    bot      = _q1("SELECT category FROM chatbots WHERE id = %s", (bot_id,))
    category = (bot or {}).get("category", "general")
    _CATEGORY_INDEXES = {
        "university": "university",
        "faculty":    "faculty",
        "fyp":        "fyp",
        "restaurant": "restaurant",
        "general":    "general",
    }
    return _CATEGORY_INDEXES.get(category, "general")


def _load_pinecone_namespace(bot_id: int):
    """
    Returns namespace as '{subscriber_id}-{bot_id}'.
    Exactly matches faculty bot pattern — isolates this bot's
    vectors from all other bots sharing the same index.
    """
    bot    = _q1("SELECT subscriber_id FROM chatbots WHERE id = %s", (bot_id,))
    sub_id = (bot or {}).get("subscriber_id", 0)
    return f"{sub_id}-{bot_id}"


# ─────────────────────────────────────────────────────────────────
# Pinecone + LLM  — shared clients, instantiated once
# ─────────────────────────────────────────────────────────────────

pc          = Pinecone(api_key=_PC_KEY)
_embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=_OAI_KEY)
llm         = ChatOpenAI(model="gpt-4o", temperature=0, api_key=_OAI_KEY)

# ─────────────────────────────────────────────────────────────────
# Per-bot context — lazily loaded + cached
# ─────────────────────────────────────────────────────────────────

_BOT_CACHE: dict = {}   # bot_id → ctx dict


def _resolve_bot_id(bot_id: Optional[int]) -> int:
    return bot_id if bot_id else DEFAULT_BOT_ID


def _get_bot_ctx(bot_id: int) -> dict:
    """
    Loads (and caches) everything needed to run this bot:
    DB row, FAQs, Pinecone index/namespace, vector store, system prompt.
    Cheap on cache hit; only hits DB + Pinecone once per bot per process.
    """
    if bot_id in _BOT_CACHE:
        return _BOT_CACHE[bot_id]

    bot      = _load_bot(bot_id)
    faqs     = _load_faqs(bot_id)
    p_index  = _load_pinecone_index(bot_id)
    p_ns     = _load_pinecone_namespace(bot_id)

    _index       = pc.Index(p_index)
    vector_store = PineconeVectorStore(
        index=_index,
        embedding=_embeddings,
        namespace=p_ns,     # always set — isolates this bot's vectors
    )

    ctx = {
        "bot_id":             bot_id,
        "bot":                bot,
        "bot_name":           bot["display_name"],
        "bot_real_name":      bot["name"],
        "category":           bot["category"],
        "org_name":           bot["org_name"],
        "owner_email":        bot["owner_email"],
        "welcome_msg":        bot["welcome_msg"],
        "faqs":               faqs,
        "pinecone_index":     p_index,
        "pinecone_namespace": p_ns,
        "vector_store":       vector_store,
    }
    ctx["system_prompt"] = _build_system_prompt(ctx)
    ctx["roasts"]        = _roasts_for(ctx["org_name"])

    _BOT_CACHE[bot_id] = ctx

    print(f"[generalBot] cached id={bot_id} name='{ctx['bot_name']}' org='{ctx['org_name']}'")
    print(f"[generalBot] index='{p_index}' namespace='{p_ns}' FAQs={len(faqs)}")

    return ctx

# ─────────────────────────────────────────────────────────────────
# System prompt  — built from DB, auto domain-aware
# ─────────────────────────────────────────────────────────────────

def _build_system_prompt(ctx: dict) -> str:
    """
    Builds the bot's identity from DB values only.
    The bot auto-detects its domain from:
      1. Its name (bot_real_name / bot_name)
      2. Its org (org_name)
      3. The document excerpts injected at runtime
    No hardcoded domain — works for any business.
    """
    BOT_REAL_NAME = ctx["bot_real_name"]
    BOT_NAME      = ctx["bot_name"]
    ORG_NAME      = ctx["org_name"]
    WELCOME_MSG   = ctx["welcome_msg"]
    FAQS          = ctx["faqs"]

    faq_block = ""
    if FAQS:
        faq_lines = "\n".join(
            f"Q: {f['question']}\nA: {f['answer']}" for f in FAQS
        )
        faq_block = f"""

FREQUENTLY ASKED QUESTIONS (reference knowledge — not a script):
{faq_lines}

FAQ ANSWERING RULES:
- These are reference facts, not text to paste verbatim into your reply.
- NEVER output the raw "Q:" / "A:" labels or list multiple FAQs back to back — always answer in natural, conversational sentences, as if you already knew the answer.
- If exactly one FAQ answers the user's question, base your reply on that FAQ's answer, reworded naturally.
- If the user's question touches multiple FAQs, merge only the relevant facts into ONE short, coherent answer — do not append unrelated FAQ answers just because they exist.
- Do not mention "FAQ" or "frequently asked questions" to the user."""

    return f"""You are {BOT_REAL_NAME}, an AI assistant created exclusively for {ORG_NAME}.
Your display name is "{BOT_NAME}".

═══ WHO YOU ARE ═══
You represent {ORG_NAME} and exist to help their customers/users.
You do not have a fixed domain. Instead you figure out what {ORG_NAME} does from:
  1. Your name "{BOT_REAL_NAME}" — this tells you which business you represent.
  2. The [Document Excerpts] in each message — your entire knowledge base.
  3. The conversation history — context from earlier in this chat.

Examples of how you adapt:
- If documents mention menu items/prices → you act as a food/restaurant assistant.
- If documents mention products/inventory → you act as a retail/e-commerce assistant.
- If documents mention services/appointments → you act as a service/booking assistant.
- If documents mention a brand/events → you act as a brand/PR assistant.
You will automatically behave correctly for {ORG_NAME}'s domain.

═══ IDENTITY RULES ═══
- If asked "who are you": say "I'm {BOT_REAL_NAME}, the AI assistant for {ORG_NAME}. How can I help?"
- If asked who made you: say you were built specifically for {ORG_NAME}.
- Never say you are ChatGPT or built by OpenAI. You are {BOT_REAL_NAME}.
- Opening welcome line: "{WELCOME_MSG}"

═══ CONVERSATION MEMORY ═══
- The full conversation history is provided above. READ IT before every reply.
- Never ask for information the user already gave in this conversation.
- Use history to correctly handle follow-up questions and references.
- If user says "the one I mentioned earlier" — check history first.

═══ KNOWLEDGE BASE RULES ═══
- For any business/domain question: answer ONLY from the [Document Excerpts] provided below.
- If the context is empty or not relevant: respond ONLY with this exact JSON:
  {{"no_context": true}}
- NEVER guess, hallucinate, or use general knowledge for business questions.
- For greetings, identity questions, small talk → respond naturally. Never return {{"no_context": true}}.
- If FAQs below answer the question → use that answer directly.

═══ LEAD CAPTURE ═══
- If a user wants to: contact {ORG_NAME}, place an order, make a booking, get a callback, or submit an inquiry:
  Step 1 — Ask for their Name (if not already known from history).
  Step 2 — Ask for their Phone (if not already known from history).
  Step 3 — Confirm their request/need.
  Once you have Name + Phone + request, respond with EXACTLY this JSON on its own line:
  {{"lead_complete": true, "name": "...", "phone": "...", "email": "", "request": "..."}}
- Never ask again for info already given earlier in the conversation.
{faq_block}
═══ TONE ═══
Warm, professional, confident. You fully represent {ORG_NAME} — act like their best employee.
Keep replies concise and helpful. Use emojis sparingly."""


# ─────────────────────────────────────────────────────────────────
# Security — prompt injection guard
# ─────────────────────────────────────────────────────────────────

_INJECT_TRIGGERS = [
    "ignore instructions", "system prompt", "jailbreak", "developer mode",
    "prompt injection", "forget everything", "previous instructions",
    "hidden instructions", "reveal", "act as", "bypass", "hack",
    "roleplay as", "simulate", "internal rules", "override",
]

def _roasts_for(org_name: str) -> list:
    return [
        f"Nice try! 😄 But I'm here to help with real questions about {org_name}.",
        f"That's not going to work — I'm laser-focused on helping you with {org_name}!",
        "I see what you're doing there. 😉 Let's keep it to legitimate questions!",
        f"Access denied! But seriously, how can I help you with {org_name}?",
        "My instructions are safe and sound. Now, what can I actually help you with?",
    ]

def _is_injection(text: str) -> bool:
    tl = text.lower()
    return any(t in tl for t in _INJECT_TRIGGERS)

# ─────────────────────────────────────────────────────────────────
# RAG pipeline
# ─────────────────────────────────────────────────────────────────

async def _retrieve_context(vector_store, query: str, k: int = 5) -> str:
    """Retrieve relevant chunks from Pinecone and return as a formatted string."""
    loop = asyncio.get_event_loop()
    try:
        docs = await loop.run_in_executor(
            None, lambda: vector_store.similarity_search(query, k=k)
        )
        if not docs:
            return ""
        return "\n\n".join(
            f"[Chunk {i+1}] {d.page_content}"
            for i, d in enumerate(docs) if d.page_content.strip()
        )
    except Exception as e:
        print(f"[retrieve] {e}")
        return ""


async def _run_chat(ctx: dict, prompt: str, history: list[dict]) -> dict:
    """
    Full chat pipeline:
    1. Retrieve context from Pinecone
    2. Build message list with full history
    3. Call LLM
    4. Parse response for signals (no_context, lead_complete)
    """
    ORG_NAME = ctx["org_name"]
    BOT_NAME = ctx["bot_name"]

    # Step 1: retrieve
    context = await _retrieve_context(ctx["vector_store"], prompt)
    ctx_block = (
        f"\n\n--- Document Excerpts ---\n{context}\n---"
        if context else ""
    )

    # Step 2: build messages — inject full history for memory
    messages = [SystemMessage(content=ctx["system_prompt"] + ctx_block)]

    for turn in history[-20:]:   # last 20 turns = full memory
        cls = HumanMessage if turn["role"] == "user" else AIMessage
        messages.append(cls(content=turn["content"]))

    messages.append(HumanMessage(content=prompt))

    # Step 3: LLM call
    loop = asyncio.get_event_loop()
    raw  = await loop.run_in_executor(None, lambda: llm.invoke(messages).content)

    # Step 4: parse signals
    no_context    = False
    lead_complete = None
    display       = raw

    # NOTE: previously this checked for two exact-spacing substrings only.
    # At any nonzero temperature the model doesn't always format this
    # identically, so it would sometimes slip through unmatched and leak
    # raw/partial JSON straight into the user-facing reply. Extracting the
    # JSON object loosely and parsing it is robust to spacing/formatting.
    no_context_m = re.search(r'\{[^{}]*"no_context"\s*:\s*true[^{}]*\}', raw, re.DOTALL)
    if no_context_m:
        try:
            json.loads(no_context_m.group(0))
            no_context = True
            display = (
                f"I don't have specific information about that in my knowledge base. "
                f"Is there something else I can help you with regarding {ORG_NAME}?"
            )
        except json.JSONDecodeError:
            pass

    # Lead capture signal
    # NOTE: previously this used a rigid regex that only matched if the LLM
    # emitted the keys in the *exact* order name -> phone -> email -> request
    # with no extra formatting. GPT-4o frequently varies key order / adds
    # whitespace / wraps it in ```json fences, which made the regex silently
    # fail to match -> lead_complete stayed None -> no DB save, no emails.
    # This version finds the JSON object loosely, then parses it with
    # json.loads so key order/whitespace/fencing no longer matter.
    lead_m = re.search(
        r'\{[^{}]*"lead_complete"\s*:\s*true[^{}]*\}', raw, re.DOTALL
    )
    if lead_m:
        try:
            lead_json = json.loads(lead_m.group(0))
        except json.JSONDecodeError as e:
            print(f"[lead-parse] Failed to parse JSON: {e} | raw: {lead_m.group(0)[:300]}")
            lead_json = None

        if lead_json:
            lead_complete = {
                "name":    lead_json.get("name", ""),
                "phone":   lead_json.get("phone", ""),
                "email":   lead_json.get("email", ""),
                "request": lead_json.get("request", ""),
            }
        display = raw[:lead_m.start()].strip()
        if lead_complete and not display:
            display = (
                f"Thank you {lead_complete['name']}! ✅ "
                f"We've received your request and {BOT_NAME} will contact you at "
                f"{lead_complete['phone']} shortly."
            )
        if lead_complete:
            # Persist lead to DB
            asyncio.create_task(_save_lead(ctx["bot_id"], lead_complete))
            # Send emails to owner and user
            task = asyncio.create_task(_send_lead_emails(ctx, lead_complete))
            def _handle_error(t):
                if t.exception():
                    print(f"[lead-email-task] Exception: {t.exception()}")
            task.add_done_callback(_handle_error)

    return {
        "reply":        display or raw,
        "no_context":   no_context,
        "lead_complete": lead_complete,
        "context_found": bool(context),
    }

# ─────────────────────────────────────────────────────────────────
# DB: persist conversation turns & leads
# ─────────────────────────────────────────────────────────────────

async def _log_turn(bot_id: int, session_id: str, user_msg: str, bot_reply: str,
                    conv_id_store: dict, channel: str = "web"):
    """Log turn to SmartChat main API (same as facultyBot)."""
    import httpx
    conv_id = conv_id_store.get(session_id)
    payload = {
        "conv_id":      conv_id,
        "user_message": user_msg,
        "bot_reply":    bot_reply,
        "topic":        user_msg[:80],
        "channel":      channel,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(
                f"{_SMARTCHAT_API}/chatbots/{bot_id}/conversations/log_turn",
                json=payload, params={"user_id": 0}
            )
            if res.status_code == 200:
                conv_id_store[session_id] = res.json().get("conv_id", conv_id)
    except Exception as e:
        print(f"[log_turn] {e}")


async def _save_lead(bot_id: int, lead: dict):
    """
    Save captured lead directly to conversations table in DB.
    Marks it with the lead details in the topic field.
    """
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: _execute("""
            INSERT INTO conversations
                (chatbot_id, customer_name, topic, status, started_at)
            VALUES (%s, %s, %s, 'active', NOW())
        """, (
            bot_id,
            lead.get("name", ""),
            f"Lead: {lead.get('request', '')} | Phone: {lead.get('phone', '')}",
        )))
        print(f"[lead] Saved: {lead.get('name')} / {lead.get('phone')}")
    except Exception as e:
        print(f"[lead save] {e}")


def _send_email(to: str, subject: str, html: str, from_name: str = "SmartChat"):
    """Send an email via SMTP."""
    if not SMTP_PASSWORD or not SMTP_EMAIL:
        print(f"[email] ✗ Missing credentials: EMAIL={bool(SMTP_EMAIL)}, PASSWORD={bool(SMTP_PASSWORD)}")
        return
    if not to or "@" not in to:
        print(f"[email] ✗ Invalid recipient: {to}")
        return
    try:
        print(f"[email] Attempting to send to {to}...")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"]    = Header(f"{from_name} <{SMTP_EMAIL}>", "utf-8")
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            print(f"[email] Connected to SMTP server")
            srv.login(SMTP_EMAIL, SMTP_PASSWORD)
            print(f"[email] Logged in successfully")
            srv.sendmail(SMTP_EMAIL, to, msg.as_string())
        print(f"[email] ✓ Sent to {to}")
    except Exception as e:
        print(f"[email] ✗ Error: {type(e).__name__}: {str(e)}")


async def _send_lead_emails(ctx: dict, lead: dict):
    """Send lead confirmation emails to owner and user."""
    ORG_NAME      = ctx["org_name"]
    OWNER_EMAIL   = ctx["owner_email"]
    BOT_REAL_NAME = ctx["bot_real_name"]
    try:
        print(f"[lead-email] Starting email send for {lead.get('name')}...")
        loop = asyncio.get_event_loop()
        ts   = datetime.now().strftime("%d %B %Y, %I:%M %p")
        name = lead.get("name", "N/A")
        email = lead.get("email", "")
        phone = lead.get("phone", "")
        request = lead.get("request", "")

        print(f"[lead-email] Lead data: name={name}, email={email}, phone={phone}, owner={OWNER_EMAIL}")

        # Build email rows
        rows = "".join(
            f"<tr><td style='color:#888;padding:10px 8px;border-bottom:1px solid #eee;font-size:13px'>"
            f"{k.title()}</td><td style='padding:10px 8px;border-bottom:1px solid #eee;"
            f"font-size:13px;font-weight:600'>{v}</td></tr>"
            for k, v in lead.items()
        )

        # Email to owner
        owner_html = f"""<html><body style='font-family:Segoe UI,sans-serif;background:#f4f6fb'>
<div style='max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden'>
<div style='background:linear-gradient(135deg,#4285F4,#34A853);padding:32px;text-align:center'>
  <h1 style='color:#fff;margin:0;font-size:22px'>🎯 New Lead Inquiry — {ORG_NAME}</h1>
  <p style='color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:13px'>{ts}</p>
</div>
<div style='padding:32px'><table style='width:100%;border-collapse:collapse'>{rows}</table></div>
</div></body></html>"""

        # Email to user
        user_html = f"""<html><body style='font-family:Segoe UI,sans-serif;background:#f4f6fb'>
<div style='max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden'>
<div style='background:linear-gradient(135deg,#4285F4,#34A853);padding:36px;text-align:center'>
  <div style='font-size:48px'>✅</div>
  <h1 style='color:#fff;margin:8px 0 0;font-size:22px'>Request Received!</h1>
  <p style='color:rgba(255,255,255,0.85);font-size:13px'>{ORG_NAME}</p>
</div>
<div style='padding:36px'>
  <p style='font-size:18px;font-weight:700;color:#1a1a2e'>Hello {name}! 👋</p>
  <p style='font-size:14px;color:#555;line-height:1.7;margin:12px 0 24px'>
    Thank you for your interest in {ORG_NAME}!<br>
    We've received your request and will contact you at <strong>{phone}</strong> within 24–48 hours.
  </p>
  <table style='width:100%;border-collapse:collapse;background:#f8f9ff;border-radius:12px'>{rows}</table>
</div></div></body></html>"""

        # Send to owner
        print(f"[lead-email] Sending to owner: {OWNER_EMAIL}")
        await loop.run_in_executor(
            None,
            _send_email,
            OWNER_EMAIL,
            f"🎯 New Lead Inquiry — {name}",
            owner_html,
            BOT_REAL_NAME,
        )

        # Send to user
        if email and "@" in email:
            print(f"[lead-email] Sending to user: {email}")
            await loop.run_in_executor(
                None,
                _send_email,
                email,
                f"✅ Request Received — {ORG_NAME}",
                user_html,
                BOT_REAL_NAME,
            )
        else:
            print(f"[lead-email] ⚠ Skipping user email (invalid: {email})")
        
        print(f"[lead-email] ✓ All emails processed for {name}")
    except Exception as e:
        print(f"[lead-email] ✗ Critical error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

# ─────────────────────────────────────────────────────────────────
# In-memory session store
# ─────────────────────────────────────────────────────────────────

sessions:  dict = {}   # session_id → list[{role, content}]
conv_ids:  dict = {}   # session_id → DB conversation id
_session_metrics = {}


def _record_response(bot_id: int, session_id: str, response_time_s: float, answered: bool):

    m = _session_metrics.setdefault(
        session_id,
        {
            "response_times": [],
            "answered": 0,
            "total": 0
        }
    )

    m["response_times"].append(response_time_s)
    m["total"] += 1
    m["answered"] += 1 if answered else 0

    avg_rt = sum(m["response_times"]) / len(m["response_times"])
    success_pct = (m["answered"] / m["total"]) * 100
    accuracy = success_pct

    _flush_metrics_to_db(bot_id, avg_rt, success_pct, accuracy)


def _flush_metrics_to_db(bot_id: int, avg_rt: float, success_rate: float, accuracy: float):
    try:
        _execute(
            """
            UPDATE chatbots
            SET response_time=%s,
                success_rate=%s,
                accuracy=%s,
                last_updated=NOW()
            WHERE id=%s
            """,
            (
                round(avg_rt, 2),
                round(success_rate, 2),
                round(accuracy, 2),
                bot_id,
            ),
        )
    except Exception as e:
        print(f"[_flush_metrics_to_db] {e}")

# ─────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────

app = FastAPI(title="SmartChat General Bot API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# ─────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message:    str
    channel:    Optional[str] = "web"
    bot_id:     Optional[int] = None

class TTSRequest(BaseModel):
    text: str

# ─────────────────────────────────────────────────────────────────
# /bot-config  — same structure as facultyBot so frontend works
# ─────────────────────────────────────────────────────────────────

@app.get("/bot-config")
async def bot_config(bot_id: Optional[int] = None):
    bid  = _resolve_bot_id(bot_id)
    loop = asyncio.get_event_loop()
    try:
        bot  = await loop.run_in_executor(None, _load_bot, bid)
        faqs = await loop.run_in_executor(None, _load_faqs, bid)
        ctx  = await loop.run_in_executor(None, _get_bot_ctx, bid)
    except RuntimeError:
        raise HTTPException(404, f"Chatbot {bid} not found")

    position  = (bot.get("position") or "bottom-right").replace("_", "-")
    shape_map = {"pill": "99px", "rounded": "12px", "square": "4px"}

    return {
        "bot_id":           bid,
        "name":             bot["display_name"],
        "real_name":        bot["name"],
        "org_name":         bot["org_name"],
        "category":         bot["category"],
        "logo_url":         bot["logo_url"] or "",
        "welcome_msg":      bot["welcome_msg"],
        "theme_color":      bot["theme_color"],
        "btn_color":        bot["btn_color"],
        "background_color": bot["background_color"],
        "text_color":       bot["text_color"],
        "theme":            bot["theme"],
        "button_shape":     bot["button_shape"],
        "btn_radius":       shape_map.get(bot["button_shape"], "12px"),
        "font_family":      bot["font_family"],
        "font_size":        int(bot["font_size"] or 14),
        "position":         position,
        "faqs":             list(faqs),
        "pinecone_index":   ctx["pinecone_index"],
        "pinecone_namespace": ctx["pinecone_namespace"],
        "plan":             bot.get("plan", "free"),
        "show_branding":    bot.get("plan", "free").lower() not in ("premium", "pro", "enterprise"),
    }

# ─────────────────────────────────────────────────────────────────
# /chat
# ─────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    import time as _time

    bid    = _resolve_bot_id(req.bot_id)
    sid    = req.session_id
    prompt = req.message.strip()
    _t_start = _time.monotonic()
    if not prompt:
        raise HTTPException(400, "Empty message")

    loop = asyncio.get_event_loop()
    try:
        ctx = await loop.run_in_executor(None, _get_bot_ctx, bid)
    except RuntimeError:
        raise HTTPException(404, f"Chatbot {bid} not found")

    sessions.setdefault(sid, [])
    history = sessions[sid]

    # ── Security guard ──
    if _is_injection(prompt):
        reply = random.choice(ctx["roasts"])
        history.append({"role": "user",      "content": prompt})
        history.append({"role": "assistant", "content": reply})
        asyncio.create_task(_log_turn(bid, sid, prompt, reply, conv_ids, channel=req.channel or "web"))
        return {
            "reply":        reply,
            "no_context":   False,
            "lead_complete": None,
            "context_found": False,
        }

    # ── RAG + LLM ──
    try:
        result = await _run_chat(ctx, prompt, history)
    except Exception as e:
        print(f"[chat] error: {e}")
        return {
            "reply":        "Sorry, something went wrong. Please try again.",
            "no_context":   False,
            "lead_complete": None,
            "context_found": False,
        }

    reply = result["reply"]

    # Save to in-memory history
    history.append({"role": "user",      "content": prompt})
    history.append({"role": "assistant", "content": reply})

    # Keep history bounded (last 40 turns)
    if len(history) > 40:
        sessions[sid] = history[-40:]

    # Log to SmartChat main API
    asyncio.create_task(_log_turn(bid, sid, prompt, reply, conv_ids, channel=req.channel or "web"))

    # Record chatbot metrics (avg response time, success rate, accuracy)
    elapsed = _time.monotonic() - _t_start
    answered = not result.get("no_context", False)

    asyncio.get_event_loop().run_in_executor(
        None, _record_response, bid, sid, elapsed, answered
    )

    return result

# ─────────────────────────────────────────────────────────────────
# /chat-history
# ─────────────────────────────────────────────────────────────────

@app.get("/chat-history/{session_id}")
async def chat_history(session_id: str):
    return {"history": sessions.get(session_id, []), "session_id": session_id}

# ─────────────────────────────────────────────────────────────────
# /tts
# ─────────────────────────────────────────────────────────────────

@app.post("/tts")
async def tts(req: TTSRequest):
    raw   = req.text.strip()
    clean = re.sub(r'\{[^}]+\}', '', raw)
    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
    clean = re.sub(r'\*(.+?)\*',    r'\1', clean)
    clean = re.sub(r'#+\s*',        '',    clean)
    clean = re.sub(r'[\U0001F000-\U0001FFFF]', '', clean)
    clean = ' '.join(clean.split())[:700]
    if not clean:
        raise HTTPException(400, "No speakable text")

    def _stream():
        client = openai.OpenAI(api_key=_OAI_KEY)
        with client.audio.speech.with_streaming_response.create(
            model="tts-1", voice="nova", input=clean,
            response_format="pcm", speed=1.0
        ) as r:
            for chunk in r.iter_bytes(4096):
                yield chunk

    return StreamingResponse(
        _stream(), media_type="audio/pcm",
        headers={"X-Sample-Rate": "24000", "X-Channels": "1", "X-Bit-Depth": "16"}
    )

def _serve_index_html() -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# ─────────────────────────────────────────────────────────────────
# / — serve frontend (default bot, e.g. local dev without an id)
# ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve():
    return _serve_index_html()

@app.get("/health")
async def health(bot_id: Optional[int] = None):
    bid  = _resolve_bot_id(bot_id)
    loop = asyncio.get_event_loop()
    try:
        ctx = await loop.run_in_executor(None, _get_bot_ctx, bid)
    except RuntimeError:
        raise HTTPException(404, f"Chatbot {bid} not found")
    return {
        "status":             "ok",
        "bot_id":             bid,
        "bot":                ctx["bot_name"],
        "org":                ctx["org_name"],
        "category":           ctx["category"],
        "pinecone_index":     ctx["pinecone_index"],
        "pinecone_namespace": ctx["pinecone_namespace"],
    }

# ─────────────────────────────────────────────────────────────────
# /{bot_id} — serve frontend for a specific bot (the URL the
# dashboard's embed/preview button generates, e.g. .../123).
# Numeric catch-all — MUST stay last so it never shadows the
# fixed-path routes above (/health, /bot-config, /chat, /tts, etc).
# ─────────────────────────────────────────────────────────────────

@app.get("/{bot_id}", response_class=HTMLResponse)
async def serve_bot(bot_id: int):
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _get_bot_ctx, bot_id)
    except RuntimeError:
        raise HTTPException(404, f"Chatbot {bot_id} not found")
    return _serve_index_html()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)