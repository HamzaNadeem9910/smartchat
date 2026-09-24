"""
Models/universityBot/main.py
University Chatbot — FastAPI Backend

Run:  uvicorn main:app --reload --port 8001
"""

import os, re, uuid, asyncio, json, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional, List, AsyncGenerator

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from pinecone import Pinecone
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
import openai

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────

def _db():
    url = os.environ.get("DATABASE_URL", "mysql+pymysql://root:@127.0.0.1/smartchat_db")
    m = re.match(r"mysql\+pymysql://([^:]*):([^@]*)@([^/:]+)(?::\d+)?/(.+)", url)
    if not m:
        raise RuntimeError(f"Cannot parse DATABASE_URL: {url}")
    user, pw, host, db = m.group(1), m.group(2), m.group(3), m.group(4)
    return pymysql.connect(host=host, user=user, password=pw or None,
                           database=db, charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor)

def _q(sql, args=()):
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()

def _q1(sql, args=()):
    rows = _q(sql, args)
    return rows[0] if rows else None

def _qw(sql, args=()):
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[_qw] DB write error: {e}")
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────────
# Load bot config from DB
# ─────────────────────────────────────────────────────────────────

# DEFAULT_BOT_ID is only used as a fallback when a request doesn't specify
# which chatbot to load. Any request that passes a chatbot id — via the URL
# path ("/123"), the "chatbot_id"/"bot_id" query string, or the "bot_id"
# field in a POST body — is served for THAT bot instead, so one running
# process (this one, on port 8001) can serve every university chatbot.
DEFAULT_BOT_ID = int(os.environ.get("BOT_ID", "1"))

def _load_bot(bot_id: int):
    bot = _q1("""
        SELECT b.id, b.name, b.category,
               s.email AS owner_email,
               COALESCE(s.plan, 'free') AS plan,
               COALESCE(c.header_title,     b.name)                  AS display_name,
               COALESCE(c.welcome_message,  'Hi! How can I help you?') AS welcome_msg,
               COALESCE(c.theme_color,      '#4f8ef7')               AS theme_color,
               COALESCE(c.button_color,     '#4f8ef7')               AS btn_color,
               COALESCE(c.background_color, '#0a0e1a')               AS background_color,
               COALESCE(c.text_color,       '#e8edf5')               AS text_color,
               COALESCE(c.theme,            'dark')                  AS theme,
               COALESCE(c.button_shape,     'rounded')               AS button_shape,
               COALESCE(c.font_family,      'DM Sans')               AS font_family,
               COALESCE(c.font_size,        14)                      AS font_size,
               COALESCE(c.position,         'bottom-right')          AS position,
               COALESCE(c.logo_url,         '')                      AS logo_url
        FROM chatbots b
        JOIN subscribers s ON s.id = b.subscriber_id
        LEFT JOIN chatbot_customization c ON c.chatbot_id = b.id
        WHERE b.id = %s
    """, (bot_id,))
    if not bot:
        raise HTTPException(404, f"Chatbot {bot_id} not found")
    return bot

def _load_faqs(bot_id: int):
    return _q("""
        SELECT question, answer, category
        FROM faqs
        WHERE chatbot_id = %s AND status = 'active'
        ORDER BY id
    """, (bot_id,))

# Fixed Pinecone index names — one shared index per category
_CATEGORY_INDEXES = {
    "university": "university",
    "faculty":    "faculty",
    "restaurant": "restaurant",
}

def _load_pinecone_index(bot_id: int):
    """
    Returns the fixed shared index name for this bot's category.
    Ignores the legacy per-bot value stored in knowledge_documents.pinecone_index.
    """
    bot = _q1("SELECT category FROM chatbots WHERE id = %s", (bot_id,))
    category = (bot or {}).get("category", "university")
    return _CATEGORY_INDEXES.get(category, "university")

def _load_pinecone_namespace(bot_id: int):
    """
    Returns the namespace that isolates this bot's vectors inside the shared index.
    Format: "{subscriber_id}-{bot_id}"  — mirrors pinecone_ingest.py _namespace().
    """
    bot = _q1("SELECT subscriber_id FROM chatbots WHERE id = %s", (bot_id,))
    user_id = (bot or {}).get("subscriber_id", 0)
    return f"{user_id}-{bot_id}"

def _load_scholarship_config(bot_id: int):
    """Load scholarship config from chatbot customization JSON if stored, else defaults."""
    row = _q1(
        "SELECT config_json FROM integrations WHERE chatbot_id = %s AND type = 'api' LIMIT 1",
        (bot_id,)
    )
    if row and row.get("config_json"):
        try:
            cfg = json.loads(row["config_json"]) if isinstance(row["config_json"], str) else row["config_json"]
            if "fsc_thresholds" in cfg:
                return cfg
        except Exception:
            pass
    return {
        "fsc_thresholds": [
            {"min": 90,  "max": 100,   "percentage": 100, "label": "Full Scholarship"},
            {"min": 80,  "max": 89.99, "percentage": 75,  "label": "75% Scholarship"},
            {"min": 70,  "max": 79.99, "percentage": 50,  "label": "50% Scholarship"},
            {"min": 60,  "max": 69.99, "percentage": 25,  "label": "25% Scholarship"},
            {"min": 0,   "max": 59.99, "percentage": 0,   "label": "No Scholarship"},
        ],
        "previous_degree_bonus": {"gold_medal": 10, "distinction": 5, "first_division": 0},
        "annual_fee": 120000,
        "currency": "PKR",
    }

# ─────────────────────────────────────────────────────────────────
# Pinecone + LLM — shared across every bot; only the index/namespace
# (looked up per bot_id) differ, so the client and the embedding/LLM
# models are created once here and reused.
# ─────────────────────────────────────────────────────────────────

_PC_KEY  = os.environ.get("PINECONE_API_KEY", "")
_OAI_KEY = os.environ.get("OPENAI_API_KEY", "")

_pc          = Pinecone(api_key=_PC_KEY) if _PC_KEY else None
_embeddings  = OpenAIEmbeddings(model="text-embedding-3-large", api_key=_OAI_KEY)
llm          = ChatOpenAI(model="gpt-4o", temperature=0.5, api_key=_OAI_KEY)

_pc_index_cache: dict = {}

def _get_pc_index(index_name: str):
    idx = _pc_index_cache.get(index_name)
    if idx is None:
        idx = _pc.Index(index_name)
        _pc_index_cache[index_name] = idx
    return idx

def _build_vector_store(index_name: str, namespace: str):
    if not index_name or not _PC_KEY:
        return None
    try:
        return PineconeVectorStore(
            index=_get_pc_index(index_name),
            embedding=_embeddings,
            namespace=namespace,
        )
    except Exception as e:
        print(f"[uni-bot] Pinecone warning: {e}")
        return None

# ─────────────────────────────────────────────────────────────────
# System prompt — built per bot from its own DB FAQs
# ─────────────────────────────────────────────────────────────────

def _faq_block(faqs: list) -> str:
    if not faqs:
        return ""
    lines = ["\n--- Frequently Asked Questions ---"]
    for f in faqs:
        lines += [f"Q: {f['question']}", f"A: {f['answer']}", ""]
    return "\n".join(lines)

def _build_system_prompt(bot_name: str, faqs: list) -> str:
    return f"""You are {bot_name} — a warm, professional university admissions assistant.
Your personality: confident, caring, friendly. Naturally mix light Urdu phrases ("ji", "bilkul", "zaroor", "acha", "shukriya") into English where it feels natural.

GREETING RULE:
If the user sends a greeting (hi, hello, salam, aoa, assalamu alaikum, etc.) respond warmly, introduce yourself briefly, and invite them to ask. Do NOT return {{"no_context": true}} for greetings.

CONTEXT RULE — PINECONE ONLY:
For any university question (programs, fees, admission, scholarships, campus, faculty, departments):
- Answer ONLY using the [Document Excerpts] context below.
- If context is empty or irrelevant, respond ONLY with the exact JSON: {{"no_context": true}}
- Do NOT guess, do NOT use general knowledge about other universities.

FAQ ANSWERS:
Use the FAQs below to answer common questions directly without needing document context.
{_faq_block(faqs)}

ADMISSION FLOW:
- When a student asks about a specific degree (BS Computer Science, MBA, etc.), answer from context, then ALWAYS end your reply with:
  {{"admission_offer": true, "degree": "<degree name>"}}
- When a student wants to apply, collect Name, Phone, Email, FSc % one at a time. When you have all four:
  {{"lead_complete": true, "name": "...", "phone": "...", "email": "...", "fsc": "...", "degree": "..."}}

SCHOLARSHIP RULE:
When asked about scholarship, ask for FSc % and previous degree achievement, calculate using the config, then present the result.

TONE: Warm, encouraging, professional. Keep responses concise. Use emojis sparingly 🎓✨"""

# ─────────────────────────────────────────────────────────────────
# Per-bot runtime context — loaded lazily on first use, then cached
# for the life of the process (same "load once" behavior as before,
# just scoped per bot_id instead of one hardcoded global bot).
# ─────────────────────────────────────────────────────────────────

_bot_ctx_cache: dict = {}

def _get_bot_ctx(bot_id: int) -> dict:
    ctx = _bot_ctx_cache.get(bot_id)
    if ctx is not None:
        return ctx

    bot   = _load_bot(bot_id)
    faqs  = _load_faqs(bot_id)
    index_name = _load_pinecone_index(bot_id)
    namespace  = _load_pinecone_namespace(bot_id)
    vector_store = _build_vector_store(index_name, namespace)

    ctx = {
        "bot_id":             bot_id,
        "name":               bot["display_name"],
        "owner_email":        bot["owner_email"],
        "theme_color":        bot["theme_color"],
        "system_prompt":      _build_system_prompt(bot["display_name"], faqs),
        "vector_store":       vector_store,
        "pinecone_index":     index_name,
        "pinecone_namespace": namespace,
    }
    _bot_ctx_cache[bot_id] = ctx
    if vector_store is not None:
        print(f"[uni-bot] loaded bot ctx id={bot_id} name='{ctx['name']}' "
              f"index='{index_name}' namespace='{namespace}'")
    else:
        print(f"[uni-bot] loaded bot ctx id={bot_id} name='{ctx['name']}' (no Pinecone)")
    return ctx

async def _ctx(bot_id: int) -> dict:
    """Async-safe accessor — cache hits return instantly; a cache miss
    (first request for a given bot_id) runs the blocking DB/Pinecone
    setup in a thread so it never stalls the event loop."""
    cached = _bot_ctx_cache.get(bot_id)
    if cached is not None:
        return cached
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_bot_ctx, bot_id)

# ─────────────────────────────────────────────────────────────────
# Scholarship config — separately cached (and mutable via PUT
# /scholarship-config) per bot_id.
# ─────────────────────────────────────────────────────────────────

_scholarship_cache: dict = {}

def _get_scholarship_config(bot_id: int) -> dict:
    cfg = _scholarship_cache.get(bot_id)
    if cfg is None:
        cfg = _load_scholarship_config(bot_id)
        _scholarship_cache[bot_id] = cfg
    return cfg

# ─────────────────────────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────────────────────────

SMTP_EMAIL    = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

def _send_email(to: str, subject: str, html: str, bot_name: str):
    if not SMTP_PASSWORD:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{bot_name} <{SMTP_EMAIL}>"
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(SMTP_EMAIL, SMTP_PASSWORD)
            srv.sendmail(SMTP_EMAIL, to, msg.as_string())
        print(f"[email] ✓ {to}")
    except Exception as e:
        print(f"[email] ✗ {e}")

async def _send_lead_emails(lead: dict, ctx: dict):
    loop = asyncio.get_event_loop()
    ts   = datetime.now().strftime("%d %B %Y, %I:%M %p")
    name = lead.get("name", "N/A")
    email = lead.get("email", "")
    bot_name    = ctx["name"]
    theme_color = ctx["theme_color"]
    owner_email = ctx["owner_email"]

    rows = "".join(
        f"<tr><td style='color:#888;padding:10px 8px;border-bottom:1px solid #eee;font-size:13px'>"
        f"{k.title()}</td><td style='padding:10px 8px;border-bottom:1px solid #eee;"
        f"font-size:13px;font-weight:600'>{v}</td></tr>"
        for k, v in lead.items() if k not in ("session_id", "bot_id")
    )

    owner_html = f"""<html><body style='font-family:Segoe UI,sans-serif;background:#f4f6fb'>
<div style='max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden'>
<div style='background:linear-gradient(135deg,{theme_color},#7c3aed);padding:32px;text-align:center'>
  <h1 style='color:#fff;margin:0;font-size:22px'>🎓 New Admission Inquiry — {bot_name}</h1>
  <p style='color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:13px'>{ts}</p>
</div>
<div style='padding:32px'><table style='width:100%;border-collapse:collapse'>{rows}</table></div>
</div></body></html>"""

    student_html = f"""<html><body style='font-family:Segoe UI,sans-serif;background:#f4f6fb'>
<div style='max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden'>
<div style='background:linear-gradient(135deg,{theme_color},#7c3aed);padding:36px;text-align:center'>
  <div style='font-size:48px'>🎓</div>
  <h1 style='color:#fff;margin:8px 0 0;font-size:22px'>Application Received!</h1>
  <p style='color:rgba(255,255,255,0.85);font-size:13px'>{bot_name}</p>
</div>
<div style='padding:36px'>
  <p style='font-size:18px;font-weight:700;color:#1a1a2e'>As-salamu Alaykum, {name}! 👋</p>
  <p style='font-size:14px;color:#555;line-height:1.7;margin:12px 0 24px'>
    Bohat shukriya for your interest in <strong>{bot_name}</strong>!
    Our admissions team will contact you within <strong>24–48 hours</strong>.
  </p>
  <table style='width:100%;border-collapse:collapse;background:#f8f9ff;border-radius:12px'>{rows}</table>
</div></div></body></html>"""

    await loop.run_in_executor(None, _send_email, owner_email,
                               f"🎓 New Admission Inquiry — {name}", owner_html, bot_name)
    if email and "@" in email:
        await loop.run_in_executor(None, _send_email, email,
                                   f"✅ Application Received — {bot_name}", student_html, bot_name)



# ─────────────────────────────────────────────────────────────────
# Log each turn to SmartChat conversations table
# ─────────────────────────────────────────────────────────────────

_SMARTCHAT_API = os.environ.get("SMARTCHAT_API", "http://127.0.0.1:8000")

async def _log_turn(session_id: str, user_msg: str, bot_reply: str, bot_id: int,
                    customer_name: str = None, customer_email: str = None,
                    channel: str = "web"):
    """Fire-and-forget: POST one turn to SmartChat backend /log_turn."""
    import httpx
    conv_id = conv_ids.get(session_id)
    payload = {
        "conv_id":        conv_id,
        "user_message":   user_msg,
        "bot_reply":      bot_reply,
        "customer_name":  customer_name,
        "customer_email": customer_email,
        "topic":          user_msg[:80],
        "channel":        channel,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(
                f"{_SMARTCHAT_API}/chatbots/{bot_id}/conversations/log_turn",
                json=payload,
                params={"user_id": 0}   # internal call — no auth check
            )
            if res.status_code == 200:
                data = res.json()
                conv_ids[session_id] = data.get("conv_id", conv_id)
    except Exception as e:
        print(f"[log_turn] warning: {e}")

# ─────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────

app = FastAPI(title="SmartChat University Bot API", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ─────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str
    channel: Optional[str] = "web"
    bot_id: Optional[int] = None   # which chatbot this message is for

class LeadInfo(BaseModel):
    session_id: str
    name:    Optional[str] = None
    phone:   Optional[str] = None
    email:   Optional[str] = None
    fsc:     Optional[str] = None
    degree:  Optional[str] = None
    bot_id:  Optional[int] = None

class ScholarshipRequest(BaseModel):
    fsc_percentage: float
    previous_degree_grade: Optional[str] = "first_division"

class ScholarshipConfigUpdate(BaseModel):
    fsc_thresholds:        list
    previous_degree_bonus: dict
    annual_fee:            float
    currency:              str

class TTSRequest(BaseModel):
    text: str

# ─────────────────────────────────────────────────────────────────
# In-memory stores
# ─────────────────────────────────────────────────────────────────

sessions:  dict = {}
leads:     dict = {}
conv_ids:  dict = {}   # session_id → conversation id in smartchat_db

_session_metrics = {}

def _record_response(session_id: str, response_time_s: float, answered: bool, bot_id: int):

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

    _flush_metrics_to_db(avg_rt, success_pct, accuracy, bot_id)


def _flush_metrics_to_db(avg_rt, success_rate, accuracy, bot_id):

    _qw(
        """
        UPDATE chatbots
        SET response_time=%s,
            success_rate=%s,
            accuracy=%s,
            last_updated=NOW()
        WHERE id=%s
        """,
        (
            round(avg_rt,2),
            round(success_rate,2),
            round(accuracy,2),
            bot_id
        )
    )
# ─────────────────────────────────────────────────────────────────
# /bot-config — frontend fetches this on load
# ─────────────────────────────────────────────────────────────────

@app.get("/bot-config")
async def bot_config(bot_id: Optional[int] = None):
    """
    Reloads ALL customization fields from DB on every call.
    This means changes saved in the SmartChat dashboard are reflected
    immediately without restarting the bot server.
    """
    bid  = bot_id or DEFAULT_BOT_ID
    loop = asyncio.get_event_loop()
    bot  = await loop.run_in_executor(None, _load_bot, bid)
    faqs = await loop.run_in_executor(None, _load_faqs, bid)
    ctx  = await _ctx(bid)

    # Normalize position: DB stores 'bottom_right', CSS uses 'bottom-right'
    position = (bot.get("position") or "bottom-right").replace("_", "-")

    return {
        "bot_id":           bid,
        "name":             bot["display_name"],
        "category":         bot["category"],
        "logo_url":         bot["logo_url"] or "",
        "welcome_msg":      bot["welcome_msg"],
        "theme_color":      bot["theme_color"],
        "btn_color":        bot["btn_color"],
        "background_color": bot["background_color"],
        "text_color":       bot["text_color"],
        "theme":            bot["theme"],
        "button_shape":     bot["button_shape"],
        "font_family":      bot["font_family"],
        "font_size":        int(bot["font_size"] or 14),
        "position":         position,
        "faqs":             faqs,
        "has_pinecone":     ctx["vector_store"] is not None,
        "has_scholarship":  True,
        "plan":             bot.get("plan", "free"),
        "show_branding":    bot.get("plan", "free").lower() not in ("premium", "pro", "enterprise"),
    }

# ─────────────────────────────────────────────────────────────────
# /chat
# ─────────────────────────────────────────────────────────────────

def _detect_lead(message: str, session_id: str, bot_id: int):
    lead = leads.get(session_id, {"session_id": session_id, "bot_id": bot_id})
    lead.setdefault("bot_id", bot_id)
    if not lead.get("phone"):
        m = re.search(r'\b(?:0|\+92)\d{10}\b|\b\d{11}\b', message)
        if m: lead["phone"] = m.group()
    if not lead.get("email"):
        m = re.search(r'[\w.+-]+@[\w-]+\.\w+', message)
        if m: lead["email"] = m.group()
    if not lead.get("name"):
        m = re.search(r'(?:my name is|i am|i\'m)\s+([A-Za-z]+(?: [A-Za-z]+){0,3})', message, re.I)
        if m: lead["name"] = m.group(1).title()
    if len(lead) > 2:   # more than just session_id + bot_id
        leads[session_id] = lead
    return lead

@app.post("/chat")
async def chat(req: ChatRequest):
    import time as _time
    _t_start = _time.monotonic()
    sid      = req.session_id
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(400, "Empty message")

    bid = req.bot_id or DEFAULT_BOT_ID
    ctx = await _ctx(bid)

    sessions.setdefault(sid, [])
    history = sessions[sid]
    _detect_lead(user_msg, sid, bid)

    # RAG
    context = ""
    if ctx["vector_store"]:
        try:
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(
                None, lambda: ctx["vector_store"].similarity_search(user_msg, k=5))
            context = "\n\n".join(d.page_content for d in docs if d.page_content.strip())
        except Exception as e:
            print(f"[retrieval] {e}")

    ctx_block = f"\n\n--- Document Excerpts ---\n{context}\n---\n" if context else ""
    msgs = [SystemMessage(content=ctx["system_prompt"] + ctx_block)]
    for t in history[-12:]:
        cls = HumanMessage if t["role"] == "user" else AIMessage
        msgs.append(cls(content=t["content"]))
    msgs.append(HumanMessage(content=user_msg))

    loop     = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: llm.invoke(msgs))
    raw      = response.content

    # Parse signals
    no_context     = False
    admission_offer = None
    lead_complete   = None
    display         = raw

    if '{"no_context": true}' in raw or '"no_context":true' in raw:
        no_context = True
        display = (
            "I'm sorry, I couldn't find relevant information about that in our database. 😊\n\n"
            "Here are some things I can help with:"
        )

    am = re.search(r'\{"admission_offer":\s*true,\s*"degree":\s*"([^"]+)"\}', raw)
    if am:
        admission_offer = {"degree": am.group(1)}
        sessions[sid + "_degree"] = am.group(1)
        display = raw[:am.start()].strip()

    lm = re.search(
        r'\{"lead_complete":\s*true,\s*"name":\s*"([^"]*)",\s*"phone":\s*"([^"]*)",'
        r'\s*"email":\s*"([^"]*)",\s*"fsc":\s*"([^"]*)",\s*"degree":\s*"([^"]*)"\}',
        raw
    )
    if lm:
        degree = sessions.get(sid + "_degree", lm.group(5))
        lead_complete = {"name": lm.group(1), "phone": lm.group(2),
                         "email": lm.group(3), "fsc": lm.group(4), "degree": degree}
        leads[sid] = {"session_id": sid, "bot_id": bid, **lead_complete}
        display = raw[:lm.start()].strip()
        asyncio.create_task(_send_lead_emails(lead_complete, ctx))

    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": display or raw})

    # Log turn to SmartChat DB (fire and forget)
    lead = leads.get(sid, {})
    asyncio.create_task(_log_turn(
        session_id     = sid,
        user_msg       = user_msg,
        bot_reply      = display or raw,
        bot_id         = bid,
        customer_name  = lead.get("name"),
        customer_email = lead.get("email"),
        channel        = req.channel or "web",
    ))

    # Record chatbot metrics
    elapsed = _time.monotonic() - _t_start
    answered = not no_context

    asyncio.get_event_loop().run_in_executor(
        None,
        _record_response,
        sid,
        elapsed,
        answered,
        bid
    )

    return {
        "reply":           display or raw,
        "session_id":      sid,
        "lead_captured":   leads.get(sid, {}),
        "context_found":   bool(context),
        "no_context":      no_context,
        "admission_offer": admission_offer,
        "lead_complete":   lead_complete,
    }
@app.get("/chat-history/{session_id}")
async def chat_history(session_id: str):
    return {"history": sessions.get(session_id, [])}

# ─────────────────────────────────────────────────────────────────
# /scholarship
# ─────────────────────────────────────────────────────────────────

@app.post("/calculate-scholarship")
async def calculate_scholarship(req: ScholarshipRequest, bot_id: Optional[int] = None):
    bid   = bot_id or DEFAULT_BOT_ID
    pct   = req.fsc_percentage
    grade = req.previous_degree_grade or "first_division"
    cfg   = _get_scholarship_config(bid)

    base, label = 0, "No Scholarship"
    for tier in cfg["fsc_thresholds"]:
        if tier["min"] <= pct <= tier["max"]:
            base, label = tier["percentage"], tier["label"]
            break

    bonus     = cfg["previous_degree_bonus"].get(grade, 0)
    total_pct = min(base + bonus, 100)
    fee       = cfg["annual_fee"]
    discount  = fee * total_pct / 100
    return {
        "total_scholarship_pct": total_pct,
        "label":                 label,
        "annual_fee":            fee,
        "discount_amount":       discount,
        "payable_amount":        fee - discount,
        "currency":              cfg["currency"],
    }

@app.get("/scholarship-config")
async def get_scholarship_config(bot_id: Optional[int] = None):
    bid = bot_id or DEFAULT_BOT_ID
    return _get_scholarship_config(bid)

@app.put("/scholarship-config")
async def update_scholarship_config(cfg: ScholarshipConfigUpdate, bot_id: Optional[int] = None):
    bid     = bot_id or DEFAULT_BOT_ID
    current = _get_scholarship_config(bid)
    current.update(cfg.model_dump())
    return {"message": "Updated", "config": current}

# ─────────────────────────────────────────────────────────────────
# /leads
# ─────────────────────────────────────────────────────────────────

@app.post("/capture-lead")
async def capture_lead(lead: LeadInfo):
    bid  = lead.bot_id or DEFAULT_BOT_ID
    ctx  = await _ctx(bid)
    data = lead.model_dump()
    data["bot_id"] = bid   # normalize so /leads filtering always finds it
    leads[lead.session_id] = data
    asyncio.create_task(_send_lead_emails(data, ctx))
    return {"message": "Lead captured", "lead": data}

@app.get("/leads")
async def get_leads(bot_id: Optional[int] = None):
    bid = bot_id or DEFAULT_BOT_ID
    filtered = [l for l in leads.values() if l.get("bot_id", DEFAULT_BOT_ID) == bid]
    return {"leads": filtered, "total": len(filtered)}

# ─────────────────────────────────────────────────────────────────
# /tts — OpenAI nova voice
# ─────────────────────────────────────────────────────────────────

@app.post("/tts")
async def tts(req: TTSRequest):
    raw = req.text.strip()
    if not raw:
        raise HTTPException(400, "Empty text")

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

# ─────────────────────────────────────────────────────────────────
# /  — serve frontend (falls back to DEFAULT_BOT_ID; the frontend JS
# resolves the actual chatbot to talk to from the URL itself)
# ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
async def health(bot_id: Optional[int] = None):
    bid = bot_id or DEFAULT_BOT_ID
    ctx = await _ctx(bid)
    return {"status": "ok", "bot_id": bid, "bot": ctx["name"],
            "pinecone_index": ctx["pinecone_index"] or "none",
            "pinecone_namespace": ctx["pinecone_namespace"]}

# ─────────────────────────────────────────────────────────────────
# /{bot_id} — serve the SAME frontend for a specific chatbot
#
# One running server (port 8001 for university bots) can now host
# every university chatbot. The dashboard's embed snippet and "live
# preview" iframe already point at http://localhost:8001/<bot_id> —
# this route is what makes that URL actually load the right bot
# instead of 404ing.
#
# Declared last, with an `:int` converter, so it can never shadow the
# fixed-path routes above (/chat, /bot-config, /tts, /scholarship-
# config, /calculate-scholarship, /capture-lead, /leads, /chat-
# history/{session_id}, /health) — those are matched first since
# they're registered earlier and aren't purely numeric.
# ─────────────────────────────────────────────────────────────────

@app.get("/{bot_id:int}", response_class=HTMLResponse)
async def serve_for_bot(bot_id: int):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)