import os, csv, json, re, random, asyncio, smtplib, uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional, List
from pathlib import Path

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import openai

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────
# DEFAULT_BOT_ID is only used as a fallback when a request doesn't specify
# which chatbot to load (e.g. hitting "/" or "/chat" with no bot_id). Any
# request that passes a chatbot id — via the URL path ("/123"), the
# "chatbot_id"/"bot_id" query string, or the "bot_id" field in a POST body —
# is served for THAT bot instead. This lets one running process (one per
# category/port, e.g. the restaurant bot on 8002) serve every restaurant
# chatbot, not just one.
DEFAULT_BOT_ID = int(os.environ.get("BOT_ID", "8"))
_PC_KEY     = os.environ.get("PINECONE_API_KEY", "")
_OAI_KEY    = os.environ.get("OPENAI_API_KEY", "")
_SMARTCHAT_API = os.environ.get("SMARTCHAT_API", "http://127.0.0.1:8000")

UPLOADS_BASE = os.environ.get(
    "UPLOADS_BASE",
    r"C:\Users\cc\Downloads\SmartChat\backend\uploads"
)

PLACEHOLDER_IMG = (
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:"
    "ANd9GcRl9d4mCkegQn_dnQFq6hiPNFcQowRaBtzacA&s"
)

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

def _load_bot(bot_id: int):
    bot = _q1("""
        SELECT b.id, b.name, b.category,
               s.email AS owner_email,
               COALESCE(s.plan, 'free')                                   AS plan,
               COALESCE(c.header_title,     b.name)                   AS display_name,
               COALESCE(c.welcome_message,  'Welcome! Ask about our menu.') AS welcome_msg,
               COALESCE(c.theme_color,      '#d4a832')                AS theme_color,
               COALESCE(c.button_color,     '#c0392b')                AS btn_color,
               COALESCE(c.background_color, '#0e0b07')                AS background_color,
               COALESCE(c.text_color,       '#f0e6d0')                AS text_color,
               COALESCE(c.theme,            'dark')                   AS theme,
               COALESCE(c.button_shape,     'rounded')                AS button_shape,
               COALESCE(c.font_family,      'DM Sans')                AS font_family,
               COALESCE(c.font_size,        14)                       AS font_size,
               COALESCE(c.position,         'bottom-right')           AS position,
               COALESCE(c.logo_url,         '')                       AS logo_url
        FROM chatbots b
        JOIN subscribers s ON s.id = b.subscriber_id
        LEFT JOIN chatbot_customization c ON c.chatbot_id = b.id
        WHERE b.id = %s
    """, (bot_id,))
    if not bot:
        raise HTTPException(404, f"Chatbot {bot_id} not found")
    return bot

def _load_faqs(bot_id: int):
    return _qa(
        "SELECT question, answer, category FROM faqs "
        "WHERE chatbot_id = %s AND status = 'active' ORDER BY id",
        (bot_id,)
    )

_CATEGORY_INDEXES = {
    "university": "university",
    "faculty":    "faculty",
    "restaurant": "restaurant",
}

def _load_pinecone_index(bot_id: int):

    bot = _q1("SELECT category FROM chatbots WHERE id = %s", (bot_id,))
    category = (bot or {}).get("category", "restaurant")
    return _CATEGORY_INDEXES.get(category, "restaurant")

def _load_pinecone_namespace(bot_id: int):

    bot = _q1("SELECT subscriber_id FROM chatbots WHERE id = %s", (bot_id,))
    user_id = (bot or {}).get("subscriber_id", 0)
    return f"{user_id}-{bot_id}"

# ─────────────────────────────────────────────────────────────────
# Pinecone + LLM — shared across every bot; only the index/namespace
# (looked up per bot_id) differ, so the client and the embedding/LLM
# models are created once here and reused.
# ─────────────────────────────────────────────────────────────────

pc           = Pinecone(api_key=_PC_KEY)
_embeddings  = OpenAIEmbeddings(model="text-embedding-3-large", api_key=_OAI_KEY)
llm          = ChatOpenAI(model="gpt-4o", temperature=0.7, api_key=_OAI_KEY)

_pc_index_cache: dict = {}

def _get_pc_index(index_name: str):
    idx = _pc_index_cache.get(index_name)
    if idx is None:
        idx = pc.Index(index_name)
        _pc_index_cache[index_name] = idx
    return idx

# ─────────────────────────────────────────────────────────────────
# System prompt — built per bot from its own DB FAQs
# ─────────────────────────────────────────────────────────────────

def _faq_block(faqs: list) -> str:
    if not faqs:
        return ""
    lines = ["\n--- FAQs ---"]
    for f in faqs:
        lines += [f"Q: {f['question']}", f"A: {f['answer']}", ""]
    return "\n".join(lines)

def _build_system_prompt(bot_name: str, faqs: list) -> str:
    return f"""You are a friendly, helpful restaurant assistant for {bot_name}.

YOUR KNOWLEDGE:
- Menu items, prices, ingredients, allergens from the [Context] below
- Branch locations, timings, delivery areas
- FAQs listed below

RULES:
1. For menu questions: answer ONLY from the [Context]. If not found, say politely it's not on the menu.
2. For greetings/general questions: respond warmly and naturally.
3. Always remember the conversation history — refer back to earlier messages when relevant.
4. When suggesting items, mention price and a brief description.
5. Use emojis naturally 🍔🌮🍕.
6. If user asks to order, help them add items to cart and collect delivery details.
{_faq_block(faqs)}
"""

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
    vector_store = PineconeVectorStore(
        index=_get_pc_index(index_name),
        embedding=_embeddings,
        namespace=namespace,
    )

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
    print(f"[restaurantBot] loaded bot ctx id={bot_id} name='{ctx['name']}' "
          f"index='{index_name}' namespace='{namespace}'")
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
# Pentest / prompt-injection detection
#
# Keyword-matched (never sent to the LLM) so a jailbreak attempt can never
# actually see the system prompt or coax the model into roleplaying outside
# its restaurant-assistant role. Caught attempts get a funny deflection
# instead of a dry refusal or an off-brand "I can't do that" — keeps the
# tone on-brand while shutting the attempt down.
# ─────────────────────────────────────────────────────────────────

PENTEST_KW = [
    "ignore previous instructions", "ignore all previous instructions",
    "ignore the above", "disregard previous", "disregard all previous",
    "system prompt", "hidden prompt", "hidden instructions",
    "reveal your instructions", "reveal your prompt", "show me your prompt",
    "show me the prompt", "show me your rules", "show me the hidden",
    "what is your prompt", "what are your instructions",
    "you are now", "act as", "pretend you are", "pretend to be",
    "roleplay as", "jailbreak", "dan mode", "developer mode",
    "bypass your", "print your instructions", "repeat your instructions",
    "forget your instructions", "forget everything above",
    "lets play a game", "let's play a game", "lets play game", "let's play game",
    "play a game", "khelte hain game", "game khelo",
]

FUNNY_DEFLECTIONS = [
    "Haha nice try, hacker sahab! 🕵️ Main sirf burgers leak karta hoon, system prompts nahi! 🍔",
    "Uh oh, penetration testing on a burger bot? My only vulnerability is extra cheese. 🧀😄",
    "Mera system prompt utna hi secret hai jitna secret sauce ka recipe — kisi ko nahi milega! 🤐🍔",
    "Nice try! Lekin main sirf ek game khel sakta hoon: 'Guess the Price of This Burger'. Ready? 😄",
    "Access denied 🚫 — lekin menu access allowed hai, wo bata dun? 😉",
    "Main ek chatbot hoon, James Bond nahi — mera koi secret mission brief nahi hai! 🍟🕶️",
    "Haan bhai, chalo game khelte hain: main sochta hoon ek food item, tum guess karo! Shuru karun? 🎮🍕",
]


def _is_pentest_attempt(text: str) -> bool:
    return any(kw in text for kw in PENTEST_KW)


def _funny_deflection() -> str:
    return random.choice(FUNNY_DEFLECTIONS)


def _merge_carts(pending: list, confirmed: list) -> list:
    """
    Combine pending_cart + cart_items without double-counting.

    The frontend sometimes echoes the same items back in both `cart_items`
    and `pending_cart` on the same request (e.g. it optimistically mirrors
    an add-to-cart into its own cart_items while the backend also keeps
    tracking the same items in pending_cart) — blindly concatenating the
    two then shows the item twice. Here, any (product, price, qty) row in
    `confirmed` that already has an identical twin in `pending` is treated
    as the same underlying entry and only counted once; anything genuinely
    different in `confirmed` (e.g. items from an earlier, separately
    finalized order in the same session) is still kept.
    """
    def _key(i):
        return (i.get("product"), i.get("price"), i.get("qty"))

    result = list(pending)
    remaining = [_key(i) for i in pending]
    for item in confirmed:
        k = _key(item)
        if k in remaining:
            remaining.remove(k)   # consume the matching duplicate, don't re-add it
            continue
        result.append(item)
    return result

# ─────────────────────────────────────────────────────────────────
# In-memory stores
# ─────────────────────────────────────────────────────────────────

sessions:  dict = {}   
conv_ids:  dict = {}   


_session_metrics: dict = {}

def _record_response(session_id: str, response_time_s: float, answered: bool, bot_id: int):

    m = _session_metrics.setdefault(
        session_id,
        {"response_times": [], "answered": 0, "total": 0}
    )
    m["response_times"].append(response_time_s)
    m["total"]    += 1
    m["answered"] += 1 if answered else 0

    avg_rt      = sum(m["response_times"]) / len(m["response_times"])
    success_pct = (m["answered"] / m["total"]) * 100

    accuracy = success_pct

    _flush_metrics_to_db(avg_rt, success_pct, accuracy, bot_id)


def _flush_metrics_to_db(avg_rt: float, success_rate: float, accuracy: float, bot_id: int):
    _qw(
        """
        UPDATE chatbots
        SET    response_time = %s,
               success_rate  = %s,
               accuracy      = %s,
               last_updated  = NOW()
        WHERE  id = %s
        """,
        (round(avg_rt, 2), round(success_rate, 2), round(accuracy, 2), bot_id)
    )

# ─────────────────────────────────────────────────────────────────
# Image path resolver
# ─────────────────────────────────────────────────────────────────

def _resolve_img(img_path: str, bot_id: int) -> str:

    if not img_path:
        return PLACEHOLDER_IMG
    if img_path.startswith("http"):
        return img_path
    p = Path(img_path)
    return f"/images/{bot_id}/{p.name}"

# ─────────────────────────────────────────────────────────────────
# Log turn to SmartChat DB
# ─────────────────────────────────────────────────────────────────

async def _log_turn(session_id: str, user_msg: str, bot_reply: str,
                    bot_id: int,
                    customer_name: str = None, customer_phone: str = None,
                    channel: str = "web"):
    import httpx
    conv_id = conv_ids.get(session_id)
    payload = {
        "conv_id":        conv_id,
        "user_message":   user_msg,
        "bot_reply":      bot_reply,
        "customer_name":  customer_name,
        "topic":          user_msg[:80],
        "channel":        channel,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(
                f"{_SMARTCHAT_API}/chatbots/{bot_id}/conversations/log_turn",
                json=payload, params={"user_id": 0}
            )
            if res.status_code == 200:
                conv_ids[session_id] = res.json().get("conv_id", conv_id)
    except Exception as e:
        print(f"[log_turn] {e}")

# ─────────────────────────────────────────────────────────────────
# Order helpers
# ─────────────────────────────────────────────────────────────────

def _vname(n): return bool(re.match(r"^[A-Za-z ]{2,}$", n))
def _vphone(p): return bool(re.match(r"^[0-9+]{10,14}$", re.sub(r"[\s\-()]", "", p)))
def _vaddr(a): return len(a.strip()) >= 5
def _vemail(e): return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e.strip()))

def _save_csv(od, ci, bot_id):
    p = "orders.csv"
    ex = os.path.isfile(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not ex:
            w.writerow(["Date", "Bot ID", "Name", "Phone", "Email", "Address", "Item", "Qty", "Price", "Total"])
        for i in ci:
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), bot_id,
                        od.get("name",""), od.get("phone",""), od.get("email",""), od.get("address",""),
                        i["product"], i["qty"], i["price"], i["price"] * i["qty"]])

# ─────────────────────────────────────────────────────────────────
# Order confirmation emails — sent to the restaurant (subscriber)
# and the customer, in place of the old Twilio WhatsApp notification.
# ─────────────────────────────────────────────────────────────────

SMTP_EMAIL    = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

def _send_email(to: str, subject: str, html: str, bot_name: str):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[email] ✗ SMTP_EMAIL/SMTP_PASSWORD not set in .env — skipping send")
        return
    if not to:
        print(f"[email] ✗ no recipient address for '{subject}' — skipping send")
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

def _order_items_rows(ci):
    return "".join(
        f"<tr>"
        f"<td style='padding:10px 8px;border-bottom:1px solid #eee;font-size:13px'>{i['product']}</td>"
        f"<td style='padding:10px 8px;border-bottom:1px solid #eee;font-size:13px;text-align:center'>{i['qty']}</td>"
        f"<td style='padding:10px 8px;border-bottom:1px solid #eee;font-size:13px;text-align:right'>Rs.{i['price']}</td>"
        f"<td style='padding:10px 8px;border-bottom:1px solid #eee;font-size:13px;text-align:right;font-weight:600'>Rs.{i['price'] * i['qty']}</td>"
        f"</tr>"
        for i in ci
    )

def _send_order_emails(od: dict, ci: list, ctx: dict):
    bot_name    = ctx["name"]
    theme_color = ctx.get("theme_color") or "#c0392b"
    owner_email = ctx.get("owner_email")
    cust_email  = od.get("email", "")
    ts    = datetime.now().strftime("%d %B %Y, %I:%M %p")
    total = sum(i["price"] * i["qty"] for i in ci)
    rows  = _order_items_rows(ci)

    items_table = f"""
    <table style='width:100%;border-collapse:collapse;background:#faf7f0;border-radius:12px;overflow:hidden'>
      <tr style='background:#f0e6d0'>
        <th style='padding:10px 8px;text-align:left;font-size:12px;color:#888'>Item</th>
        <th style='padding:10px 8px;text-align:center;font-size:12px;color:#888'>Qty</th>
        <th style='padding:10px 8px;text-align:right;font-size:12px;color:#888'>Price</th>
        <th style='padding:10px 8px;text-align:right;font-size:12px;color:#888'>Subtotal</th>
      </tr>
      {rows}
    </table>
    <div style='text-align:right;margin-top:14px;font-size:16px;font-weight:700;color:#1a1a1a'>
      Total: Rs.{total}
    </div>"""

    owner_html = f"""<html><body style='font-family:Segoe UI,sans-serif;background:#f4f6fb'>
<div style='max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden'>
<div style='background:linear-gradient(135deg,{theme_color},#7c3aed);padding:32px;text-align:center'>
  <h1 style='color:#fff;margin:0;font-size:22px'>🍽️ New Order — {bot_name}</h1>
  <p style='color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:13px'>{ts}</p>
</div>
<div style='padding:32px'>
  <table style='width:100%;border-collapse:collapse;margin-bottom:20px'>
    <tr><td style='color:#888;padding:6px 0;font-size:13px'>Name</td><td style='padding:6px 0;font-size:13px;font-weight:600'>{od.get('name','')}</td></tr>
    <tr><td style='color:#888;padding:6px 0;font-size:13px'>Phone</td><td style='padding:6px 0;font-size:13px;font-weight:600'>{od.get('phone','')}</td></tr>
    <tr><td style='color:#888;padding:6px 0;font-size:13px'>Email</td><td style='padding:6px 0;font-size:13px;font-weight:600'>{cust_email or '—'}</td></tr>
    <tr><td style='color:#888;padding:6px 0;font-size:13px'>Address</td><td style='padding:6px 0;font-size:13px;font-weight:600'>{od.get('address','')}</td></tr>
  </table>
  {items_table}
</div>
<div style='padding:16px 32px;background:#f8f9ff;text-align:center;font-size:11px;color:#999'>
  Sent automatically by {bot_name}
</div>
</div></body></html>"""

    customer_html = f"""<html><body style='font-family:Segoe UI,sans-serif;background:#f4f6fb'>
<div style='max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden'>
<div style='background:linear-gradient(135deg,{theme_color},#7c3aed);padding:36px;text-align:center'>
  <div style='font-size:48px'>🍽️</div>
  <h1 style='color:#fff;margin:8px 0 0;font-size:22px'>Order Confirmed!</h1>
  <p style='color:rgba(255,255,255,0.85);font-size:13px'>{bot_name}</p>
</div>
<div style='padding:36px'>
  <p style='font-size:18px;font-weight:700;color:#1a1a2e'>Shukriya, {od.get('name','')}! 🎉</p>
  <p style='font-size:14px;color:#555;line-height:1.7;margin:12px 0 24px'>
    Your order from <strong>{bot_name}</strong> has been received and is being prepared.
    It will be delivered to <strong>{od.get('address','')}</strong>.
  </p>
  {items_table}
</div>
<div style='padding:16px 32px;background:#f8f9ff;text-align:center;font-size:11px;color:#999'>
  This is an automated receipt from {bot_name}
</div>
</div></body></html>"""

    _send_email(owner_email, f"🍽️ New Order — {od.get('name','')}", owner_html, bot_name)
    if cust_email and _vemail(cust_email):
        _send_email(cust_email, f"✅ Order Confirmed — {bot_name}", customer_html, bot_name)

# ─────────────────────────────────────────────────────────────────
# TTS text cleaner
# ─────────────────────────────────────────────────────────────────

def _strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",    r"\1", text)
    text = re.sub(r"^#{1,4}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"ITEMS:\[[^\]]*\]", "", text)
    return text.strip()


def _clean_for_tts(text: str) -> str:
    text = re.sub(r'\{[^}]+\}', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*',    r'\1', text)
    text = re.sub(r'#+\s*',        '',    text)
    text = re.sub(r'[\U0001F000-\U0001FFFF]', '', text)
    text = re.sub(r'Rs\.?\s*\d+', lambda m: m.group().replace('Rs.', 'Rupees '), text)
    text = ' '.join(text.split())
    return text[:700]

# ─────────────────────────────────────────────────────────────────
# FastAPI
# ─────────────────────────────────────────────────────────────────

app = FastAPI(title="SmartChat Restaurant Bot API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# Images used to be mounted once from a single bot's upload folder at
# startup. Since this process now serves many bots, images are served
# per-bot instead via the GET /images/{bot_id}/{filename} route defined
# further down (after the pydantic models / other routes).

# ─────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id:              str
    message:                 str
    cart_items:              list = []
    order_details:           dict = {}
    awaiting_order_details:  bool = False
    current_field:           Optional[str] = None
    pending_cart:            list = []
    awaiting_confirmation:   bool = False
    channel:                 str = "web"
    bot_id:                  Optional[int] = None   # which chatbot this message is for

class OrderFinalizeRequest(BaseModel):
    session_id:    str
    order_details: dict
    cart_items:    list
    bot_id:        Optional[int] = None

class TTSRequest(BaseModel):
    text: str

# ─────────────────────────────────────────────────────────────────
# /bot-config 
# ─────────────────────────────────────────────────────────────────

@app.get("/bot-config")
async def bot_config(bot_id: Optional[int] = None):
    bid  = bot_id or DEFAULT_BOT_ID
    loop = asyncio.get_event_loop()
    bot  = await loop.run_in_executor(None, _load_bot, bid)
    faqs = await loop.run_in_executor(None, _load_faqs, bid)
    position = (bot.get("position") or "bottom-right").replace("_", "-")
    shapeMap = {"pill": "99px", "rounded": "12px", "square": "4px"}
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
        "btn_radius":       shapeMap.get(bot["button_shape"], "12px"),
        "font_family":      bot["font_family"],
        "font_size":        int(bot["font_size"] or 14),
        "position":         position,
        "faqs":             list(faqs),
        "has_pinecone":     True,
        "plan":             bot.get("plan", "free"),
        "hide_branding":    bot.get("plan", "free").lower() in ("premium", "pro", "enterprise"),
    }

# ─────────────────────────────────────────────────────────────────
# /chat — with full conversation history
# ─────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    import time as _time
    _t_start = _time.monotonic()

    bid = req.bot_id or DEFAULT_BOT_ID
    ctx = await _ctx(bid)

    sid    = req.session_id
    prompt = req.message.strip()
    pl     = prompt.lower()

    # Init session history
    sessions.setdefault(sid, [])
    history = sessions[sid]

    # ── Keywords ──
    YES = {"yes","haan","ha","ok","okay","confirm","proceed","ji","bilkul","sure","yep","kar do","theek hai"}
    NO  = {"no","nahi","na","nope","cancel","mat karo","nai"}
    ORDER_KW    = ["order","buy","chahiye","kardo","add","bhej do","want","send me","lena hai","de do"]
    CHECKOUT_KW = ["checkout","proceed","confirm order","place order","finalize","order these","my order","yahi chahiye"]

    is_yes      = any(w in pl for w in YES)
    is_no       = any(w in pl for w in NO)
    is_order    = any(kw in pl for kw in ORDER_KW)
    is_checkout = any(kw in pl for kw in CHECKOUT_KW)
    all_cart    = _merge_carts(req.pending_cart, req.cart_items)

    def _reply(type_, message, **kwargs):
        """Helper — saves history, fires metrics, and returns response."""
        history.append({"role": "user",      "content": prompt})
        history.append({"role": "assistant", "content": message})
        sessions[sid] = history[-30:]  

        elapsed  = _time.monotonic() - _t_start
        FALLBACK_SIGNALS = [
            "nahi hai", "not on the menu", "available nahi", "nahi milta",
            "menu mein nahi", "pata nahi", "i don't know", "not available",
            "koi item available nahi",
        ]
        answered = not any(s in message.lower() for s in FALLBACK_SIGNALS)
        asyncio.get_event_loop().run_in_executor(
            None, _record_response, sid, elapsed, answered, bid
        )

        asyncio.create_task(_log_turn(sid, prompt, message, bid,
                                      req.order_details.get("name"),
                                      req.order_details.get("phone"),
                                      req.channel))
        return {"type": type_, "message": message, **kwargs}

    # ── Pentest / prompt-injection attempt → funny deflection, never hits the LLM ──
    if _is_pentest_attempt(pl):
        return _reply("text", _funny_deflection(), state={})

    def _llm_history():
        """Build LangChain messages from session history."""
        msgs = [SystemMessage(content=ctx["system_prompt"])]
        for turn in history[-16:]:
            cls = HumanMessage if turn["role"] == "user" else AIMessage
            msgs.append(cls(content=turn["content"]))
        return msgs

    # ── Order confirmation flow ──
    if req.awaiting_confirmation:
        if is_yes and all_cart:
            return _reply("order_start", "Apka naam batayein? 😊",
                          state={"awaiting_order_details": True,
                                 "current_field": "name",
                                 "awaiting_confirmation": False})
        elif is_no:
            return _reply("text", "Koi baat nahi! Kuch aur chahiye? 😊",
                          state={"awaiting_confirmation": False})
        else:
            total = sum(i["price"] * i["qty"] for i in all_cart)
            return _reply("text",
                          f"Please Yes ya No likhein. (Total: Rs.{total})",
                          state={})

    # ── Order detail collection ──
    if req.awaiting_order_details and req.current_field:
        f = req.current_field
        od = req.order_details

        if f == "name":
            if _vname(prompt):
                return _reply("order_collection", "Phone number? 📞",
                              state={"order_details": {**od, "name": prompt},
                                     "current_field": "phone"})
            return _reply("order_collection", "Sirf naam likhein (e.g. Ali Ahmed):",
                          state={"current_field": "name"})

        if f == "phone":
            clean_phone = re.sub(r"[\s\-()]", "", prompt)
            # Accept +92XXXXXXXXXX or 03XXXXXXXXX
            if _vphone(clean_phone):
                return _reply("order_collection", "Email address (order receipt ke liye)? 📧",
                              state={"order_details": {**od, "phone": clean_phone},
                                     "current_field": "email"})
            return _reply("order_collection",
                          "Phone number format: +923001234567 ya 03001234567",
                          state={"current_field": "phone"})

        if f == "email":
            if _vemail(prompt):
                return _reply("order_collection", "Delivery address? 📍",
                              state={"order_details": {**od, "email": prompt.strip()},
                                     "current_field": "address"})
            return _reply("order_collection",
                          "Sahi email likhein (e.g. ali@example.com):",
                          state={"current_field": "email"})

        if f == "address":
            if _vaddr(prompt):
                merged = _merge_carts(req.pending_cart, req.cart_items)
                return _reply("order_collection",
                              "✅ Details save ho gaye! 60 seconds mein auto-confirm hoga.",
                              state={"order_details": {**od, "address": prompt},
                                     "cart_items": merged,
                                     "pending_cart": [],
                                     "awaiting_order_details": False,
                                     "current_field": None,
                                     "timer_active": True})
            return _reply("order_collection",
                          "Address thoda aur detail mein likhein (mohalla, city):",
                          state={"current_field": "address"})

    # ── RAG retrieval ──
    loop = asyncio.get_event_loop()
    docs = await loop.run_in_executor(
        None,
        lambda: ctx["vector_store"].as_retriever(
            search_type="similarity", search_kwargs={"k": 30}
        ).invoke(prompt)
    )
    docs_text = "\n".join([d.page_content for d in docs])

    # ── Checkout ──
    if is_checkout and all_cart:
        total = sum(i["price"] * i["qty"] for i in all_cart)
        lines = "\n".join([f"• {i['qty']}x {i['product']} = Rs.{i['price']*i['qty']}"
                           for i in all_cart])
        return _reply("cart_summary",
                      f"📋 Order Summary:\n{lines}\n\n💰 Total: Rs.{total}\n\nConfirm karein? (Yes/No)",
                      cart=all_cart, total=total,
                      state={"awaiting_confirmation": True})

    # ── Price range filter ──
    range_m = re.search(r"(\d+)\s*(se|to|-)\s*(\d+)", prompt, re.I)
    above_m = re.search(r"(above|upar|more than)\s*(\d+)", prompt, re.I)
    budgt_m = re.search(r"(\d+)\s*(mein|men|budget|pkr|rs\.?)", prompt, re.I)

    if range_m or above_m or budgt_m:
        items = [{"name": d.metadata.get("item_name",""),
                  "price": float(d.metadata.get("price", 0) or 0),
                  "metadata": d.metadata}
                 for d in docs if d.metadata.get("item_name")]
        if range_m:
            lo, hi = float(range_m.group(1)), float(range_m.group(3))
            price_filtered = [i for i in items if lo <= i["price"] <= hi]
        elif above_m:
            price_filtered = [i for i in items if i["price"] > float(above_m.group(2))]
        else:
            price_filtered = [i for i in items if i["price"] <= float(budgt_m.group(1))]

        # ── Detect category from recent conversation history ──
        CATEGORY_KEYWORDS = {
            "burger":  ["burger", "burgers"],
            "pizza":   ["pizza", "pizzas"],
            "wrap":    ["wrap", "wraps"],
            "drink":   ["drink", "drinks", "shake", "shakes", "juice", "lime", "lemonade"],
            "fries":   ["fries", "chips"],
            "dessert": ["dessert", "sweet", "cookie", "churro", "meetha"],
            "breakfast": ["breakfast"],
            "combo":   ["combo", "meal", "deal"],
        }

        detected_category = None
        # Check last 6 history turns for a food category mention
        for turn in reversed(history[-6:]):
            turn_text = turn["content"].lower()
            for cat, keywords in CATEGORY_KEYWORDS.items():
                if any(kw in turn_text for kw in keywords):
                    detected_category = cat
                    break
            if detected_category:
                break

        if detected_category:
            category_filtered = [
                i for i in price_filtered
                if detected_category in (i["metadata"].get("category") or i["metadata"].get("item_type") or i["name"] or "").lower()
            ]
            filtered = category_filtered if category_filtered else price_filtered
        else:
            filtered = price_filtered

        if filtered:
            layout = [{"name": i["name"], "price": i["price"],
                       "desc": i["metadata"].get("description", ""),
                       "img": _resolve_img(i["metadata"].get("image_path",""), bid)}
                      for i in filtered]
            if range_m:
                filter_desc = f"between Rs.{int(float(range_m.group(1)))} and Rs.{int(float(range_m.group(3)))}"
            elif above_m:
                filter_desc = f"above Rs.{int(float(above_m.group(2)))}"
            else:
                filter_desc = f"within budget of Rs.{int(float(budgt_m.group(1)))}"

            filtered_names = ", ".join([i["name"] for i in filtered])
            price_filter_prompt = (
                f"{ctx['system_prompt']}\n\n"
                f"[Context] Items available {filter_desc}: {filtered_names}\n\n"
                f"User asked: {prompt}\n\n"
                f"Instructions:\n"
                f"1. Refer to the conversation history naturally — if user previously asked about a specific category (e.g. burgers, drinks, wraps), mention that context.\n"
                f"2. Introduce the filtered items in a friendly, context-aware way using the correct filter type ({filter_desc}).\n"
                f"3. Keep it concise. Do NOT use markdown or **bold**.\n"
                f"4. Use Urdu/English mix naturally."
            )
            price_msgs = [SystemMessage(content=price_filter_prompt)]
            for turn in history[-16:]:
                cls = HumanMessage if turn["role"] == "user" else AIMessage
                price_msgs.append(cls(content=turn["content"]))
            price_msgs.append(HumanMessage(content=prompt))
            price_answer = await loop.run_in_executor(None, lambda: llm.invoke(price_msgs).content)
            price_answer = _strip_md(price_answer)
            return _reply("menu_items", price_answer, items=layout, state={})
        return _reply("text", "Is price filter mein koi item available nahi. Koi aur price try karein!", state={})

    # ── Order intent ──
    if is_order:
        valid = {
            d.metadata.get("item_name","").strip().lower(): {
                "full_name": d.metadata.get("item_name",""),
                "price": d.metadata.get("price", 0),
                "metadata": d.metadata,
            }
            for d in docs if d.metadata.get("item_name")
        }
        menu_str = "\n".join([f"- {v['full_name']}: Rs.{v['price']}"
                               for v in valid.values()])
        raw = await loop.run_in_executor(None, lambda: llm.invoke([
            SystemMessage(content=(
                f"Extract ordered items as JSON from user message.\n"
                f"Valid menu items:\n{menu_str}\n"
                f'Return ONLY: {{"cart":[{{"product":"Name","price":0,"qty":1}}]}}'
            )),
            HumanMessage(content=prompt),
        ]).content)
        try:
            m2 = re.search(r"\{.*\}", raw, re.DOTALL)
            new_items = json.loads(m2.group(0)).get("cart", []) if m2 else []
        except Exception:
            new_items = []

        enriched = []
        for item in new_items:
            key = item.get("product","").lower()
            if key in valid:
                meta = valid[key]["metadata"]
                enriched.append({
                    "product": valid[key]["full_name"],
                    "price": float(valid[key]["price"] or 0),
                    "qty": item.get("qty", 1),
                    "img": _resolve_img(meta.get("image_path",""), bid),
                })

        if enriched:
            np2   = list(req.pending_cart) + enriched
            total = sum(i["price"] * i["qty"] for i in np2)
            lines = "\n".join([f"• {i['qty']}x {i['product']} = Rs.{i['price']*i['qty']}"
                               for i in np2])
            return _reply("order_start",
                          f"🛒 Cart mein add ho gaya!\n{lines}\n\n💰 Total: Rs.{total}\n\nKuch aur chahiye ya checkout karna hai? 😊",
                          new_items=enriched,
                          state={"pending_cart": np2})
        return _reply("text", "Yeh item menu mein nahi hai. Koi aur item try karein! 😊", state={})

    # ── General query with history + RAG context ──
    dlookup = {}
    for d in docs:
        name = d.metadata.get("item_name", "").strip()
        if name:
            dlookup[name.lower()] = d.metadata

    # Detect if this is a menu/food query using keyword heuristics FIRST
    # This avoids a slow extra LLM call for obvious food queries
    FOOD_KW = [
        "menu", "kya hai", "kia hai", "kya h", "kia h", "kya hy", "kia hy",
        "items", "dish", "food", "available", "milta", "milti", "offer",
        "burger", "wrap", "chicken", "beef", "fries", "shake", "drink",
        "dessert", "meetha", "mithai", "mithe", "sweet", "cookie", "churro",
        "breakfast", "lunch", "dinner", "snack", "meal", "combo",
        "price", "rate", "kitna", "cost", "kitne ka", "rs", "pkr",
        "show", "list", "batao", "bata", "dekha", "dekho","pizza",'party','family','kids',
        'special','offer','deals','deal','discount','sale','spicy','tasty','fresh','hot',
        'cold','sweet','sour','salty','bitter','umami','crispy','soft','cheesy','creamy',
        'grilled','fried','baked','roasted','steamed'
    ]
    is_food_query = any(kw in pl for kw in FOOD_KW) and bool(dlookup)

    context_sys = (f"{ctx['system_prompt']}\n\n[Context]\n{docs_text}"
                   if docs_text.strip() else ctx['system_prompt'])
    msgs = [SystemMessage(content=context_sys)]
    for turn in history[-16:]:
        cls = HumanMessage if turn["role"] == "user" else AIMessage
        msgs.append(cls(content=turn["content"]))
    msgs.append(HumanMessage(content=prompt))

    if is_food_query:
        # Single LLM call: get the answer AND a list of relevant item names
        combined_prompt = (
            f"{context_sys}\n\n"
            f"User asks: {prompt}\n\n"
            f"Instructions:\n"
            f"1. Answer the question naturally in plain text. Do NOT use ** or markdown.\n"
            f"2. After your answer, on a NEW LINE output EXACTLY: ITEMS:[name1|name2|name3]\n"
            f"   listing the item_names from context that are relevant to this query.\n"
            f"3. If no specific items match, output ITEMS:[]\n"
            f"4. Use Urdu/English mix naturally. Keep response concise."
        )
        full_msgs = [SystemMessage(content=combined_prompt)]
        for turn in history[-16:]:
            cls = HumanMessage if turn["role"] == "user" else AIMessage
            full_msgs.append(cls(content=turn["content"]))
        full_msgs.append(HumanMessage(content=prompt))

        raw_answer = await loop.run_in_executor(None, lambda: llm.invoke(full_msgs).content)

        answer_text = raw_answer
        item_names  = []
        items_match = re.search(r"ITEMS:\[([^\]]*)\]", raw_answer)
        if items_match:
            answer_text = raw_answer[:items_match.start()].strip()
            names_str   = items_match.group(1).strip()
            if names_str:
                item_names = [n.strip() for n in names_str.split("|") if n.strip()]

        answer_text = _strip_md(answer_text)

        unique = []
        seen   = set()
        for name in item_names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            meta = dlookup.get(key)
            if not meta:
                for k, v in dlookup.items():
                    if name.lower() in k or k in name.lower():
                        meta = v
                        break
            if meta:
                try:
                    price = float(meta.get("price", 0) or 0)
                except Exception:
                    price = 0
                unique.append({
                    "name":  meta.get("item_name", name),
                    "price": price,
                    "desc":  meta.get("description", "Freshly prepared."),
                    "img":   _resolve_img(meta.get("image_path", ""), bid),
                })

        if unique:
            return _reply("menu_items", answer_text, items=unique, state={})
        return _reply("text", answer_text, state={})

    answer = await loop.run_in_executor(None, lambda: llm.invoke(msgs).content)
    return _reply("text", _strip_md(answer), state={})

# ─────────────────────────────────────────────────────────────────
# /finalize
# ─────────────────────────────────────────────────────────────────

@app.post("/finalize")
async def finalize(req: OrderFinalizeRequest):
    bid = req.bot_id or DEFAULT_BOT_ID
    ctx = await _ctx(bid)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _save_csv, req.order_details, req.cart_items, bid)
    await loop.run_in_executor(None, _send_order_emails, req.order_details, req.cart_items, ctx)
    total = sum(i["price"] * i["qty"] for i in req.cart_items)
    return {"success": True, "message": "✅ Order confirmed!", "total": total}

@app.delete("/cancel")
async def cancel():
    return {"success": True, "message": "Order cancelled."}

# ─────────────────────────────────────────────────────────────────
# /tts 
# ─────────────────────────────────────────────────────────────────

@app.post("/tts")
async def tts(req: TTSRequest):
    clean = _clean_for_tts(req.text)
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
# /images/{bot_id}/{filename} — per-bot image serving
#
# Replaces the old single static mount now that one process serves
# many bots' uploads folders.
# ─────────────────────────────────────────────────────────────────

@app.get("/images/{bot_id}/{filename}")
async def serve_image(bot_id: int, filename: str):
    images_dir = os.path.join(UPLOADS_BASE, str(bot_id), "images")
    file_path  = os.path.normpath(os.path.join(images_dir, filename))
    if not file_path.startswith(os.path.normpath(images_dir) + os.sep) or not os.path.isfile(file_path):
        raise HTTPException(404, "Image not found")
    return FileResponse(file_path)

# ─────────────────────────────────────────────────────────────────
# / — serve frontend (falls back to DEFAULT_BOT_ID; the frontend JS
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
            "pinecone_index": ctx["pinecone_index"],
            "pinecone_namespace": ctx["pinecone_namespace"]}

# ─────────────────────────────────────────────────────────────────
# /{bot_id} — serve the SAME frontend for a specific chatbot
#
# One running server (one port per category, e.g. 8002 for
# restaurants) can now host every bot in that category. The
# dashboard's embed snippet and "live preview" iframe already point
# at http://localhost:<port>/<bot_id> — this route is what makes
# that URL actually load the right bot instead of 404ing.
#
# Declared last, with an `:int` converter, so it can never shadow
# the fixed-path routes above (/chat, /bot-config, /tts, /finalize,
# /cancel, /health, /images/...) — those are matched first since
# they're registered earlier and aren't purely numeric.
# ─────────────────────────────────────────────────────────────────

@app.get("/{bot_id:int}", response_class=HTMLResponse)
async def serve_for_bot(bot_id: int):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)