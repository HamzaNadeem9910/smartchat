"""
WhatsApp integration router for SmartChat.

Copy this file to backend/routers/whatsapp.py, then wire it into main.py:

    from routers import whatsapp
    app.include_router(whatsapp.router)

Adjust the chatbot-pipeline import/call in `handle_incoming_message` below to
match your actual per-category bot logic.
"""

import os
import re
import json
import asyncio
import uuid
import base64
import io
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import text

from database import get_db
from models import WhatsAppSession, Integration, IntegrationType, IntegrationStatus

# PDF text extraction for transcripts sent as WhatsApp documents.
# pip install pypdf --break-system-packages  (if not already installed)
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:4001")
try:
    BOT_SERVICE_URLS = json.loads(os.getenv("BOT_SERVICE_URLS", "{}"))
except json.JSONDecodeError:
    BOT_SERVICE_URLS = {}


def bot_service_url(port: int, path: str) -> str:
    base_url = BOT_SERVICE_URLS.get(str(port), f"http://localhost:{port}").rstrip("/")
    return f"{base_url}/{path.lstrip('/')}"

# Each bot category runs as its own FastAPI process on its own port — same
# mapping DashboardPage.tsx uses to build the iframe embed snippet.
CATEGORY_PORT_MAP = {
    "university": 8001,
    "restaurant": 8002,
    "faculty":    8003,
    "fyp":        8004,
    "general":    8005,
}

# Per-WhatsApp-sender order state (cart, awaiting_confirmation, etc). The
# bot's own /chat endpoint is stateless w.r.t. ordering — it expects the
# caller to hand back whatever `state` it returned on the previous turn.
# The web widget does this in the browser; here we do it in memory, keyed
# by (bot_id, sender), since one WhatsApp number could message more than
# one bot. Fine for a demo; swap for Redis/DB if the service restarts a lot.
_whatsapp_order_state: dict = {}

ORDER_STATE_FIELDS = (
    "cart_items", "order_details", "awaiting_order_details",
    "current_field", "pending_cart", "awaiting_confirmation",
)

# The web widget's 60s auto-confirm is a JS setTimeout in the browser that
# calls /finalize once it elapses — WhatsApp has no browser to run that, so
# we run the equivalent countdown here instead. Keyed by (bot_id, sender);
# each new timer overwrites the token so a stale/earlier countdown can't
# fire after a newer order supersedes it.
_whatsapp_timer_tokens: dict = {}

# Same Urdu/English confirm vocabulary as the YES set in the bot's own
# main.py, so a customer typing "confirm" or "ok" during the WhatsApp
# countdown finalizes immediately instead of waiting the full 60s.
_CONFIRM_WORDS = {"yes", "haan", "ha", "ok", "okay", "confirm", "proceed", "ji", "bilkul", "sure", "yep"}
_CONFIRM_PHRASES = ("kar do", "theek hai", "confirm order", "place order")


def _is_confirm_signal(text: str) -> bool:
    t = (text or "").strip().lower()
    if any(p in t for p in _CONFIRM_PHRASES):
        return True
    return bool(set(re.findall(r"[a-z]+", t)) & _CONFIRM_WORDS)


def _get_bot_port(db: Session, bot_id: int) -> int:
    row = db.execute(
        text("SELECT category FROM chatbots WHERE id = :bot_id"),
        {"bot_id": bot_id},
    ).mappings().first()
    category = (row or {}).get("category", "general")
    return CATEGORY_PORT_MAP.get(category, CATEGORY_PORT_MAP["general"])


class IncomingMessage(BaseModel):
    bot_id: int
    sender: str
    message: str = ""
    # Optional attached document (e.g. a transcript PDF), forwarded from
    # whatsapp-service when the inbound message is a document, not text.
    file_base64: Optional[str] = None
    file_name: Optional[str] = None
    file_mime: Optional[str] = None


class StatusUpdate(BaseModel):
    bot_id: int
    status: str
    phone_number: Optional[str] = None


def _extract_pdf_text(file_base64: str, max_chars: int = 12000) -> str:
    """Extract text from a base64-encoded PDF (e.g. a transcript sent as a
    WhatsApp document). Returns '' if extraction fails or pypdf isn't
    installed, so callers can fall back gracefully."""
    if not PdfReader:
        print("[whatsapp] pypdf not installed — run: pip install pypdf --break-system-packages")
        return ""
    try:
        raw = base64.b64decode(file_base64)
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        text_out = "\n".join(pages).strip()
        return text_out[:max_chars]
    except Exception as e:
        print(f"[whatsapp] PDF extraction failed: {e}")
        return ""


def _sync_integration_status(db: Session, bot_id: int, status: str) -> None:
    """Mirror the WhatsApp session status onto the shared `integrations` row.

    The dashboard's Integrations tab reads from the `integrations` table
    (one row per chatbot per type), not from `whatsapp_sessions` — so without
    this, the WhatsApp card in the UI would never actually flip to
    "Connected" no matter what Baileys reports.
    """
    status_map = {
        "connected": IntegrationStatus.connected,
        "disconnected": IntegrationStatus.disconnected,
    }
    mapped = status_map.get(status, IntegrationStatus.pending)

    row = db.query(Integration).filter_by(chatbot_id=bot_id, type=IntegrationType.whatsapp).first()
    if not row:
        row = Integration(chatbot_id=bot_id, type=IntegrationType.whatsapp)
        db.add(row)

    row.status = mapped
    if mapped == IntegrationStatus.connected and not row.connected_at:
        row.connected_at = datetime.utcnow()
    db.commit()


@router.post("/sessions/{bot_id}/start")
async def start_whatsapp_session(bot_id: int, db: Session = Depends(get_db)):
    """Owner clicks 'Connect WhatsApp' in the dashboard. Creates/reuses a DB
    record and asks whatsapp-service to spin up (or reuse) a Baileys session."""
    session = db.query(WhatsAppSession).filter_by(bot_id=bot_id).first()
    if not session:
        session = WhatsAppSession(bot_id=bot_id, status="pending")
        db.add(session)
        db.commit()
        db.refresh(session)

    _sync_integration_status(db, bot_id, "pending")

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{WHATSAPP_SERVICE_URL}/session/{bot_id}/start", timeout=30)
        resp.raise_for_status()
        return resp.json()  # { status, qr, phoneNumber }


@router.get("/sessions/{bot_id}/status")
async def get_whatsapp_status(bot_id: int):
    """Dashboard polls this every few seconds while the QR modal is open."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{WHATSAPP_SERVICE_URL}/session/{bot_id}/status", timeout=10)
        resp.raise_for_status()
        return resp.json()


@router.delete("/sessions/{bot_id}")
async def disconnect_whatsapp(bot_id: int, db: Session = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{WHATSAPP_SERVICE_URL}/session/{bot_id}", timeout=10)

    session = db.query(WhatsAppSession).filter_by(bot_id=bot_id).first()
    if session:
        session.status = "disconnected"
        db.commit()

    _sync_integration_status(db, bot_id, "disconnected")
    return {"ok": True}


@router.post("/status")
def update_status_from_service(payload: StatusUpdate, db: Session = Depends(get_db)):
    """Called by whatsapp-service whenever a session connects/disconnects."""
    session = db.query(WhatsAppSession).filter_by(bot_id=payload.bot_id).first()
    if not session:
        session = WhatsAppSession(bot_id=payload.bot_id)
        db.add(session)

    session.status = payload.status
    if payload.phone_number:
        session.phone_number = payload.phone_number
    db.commit()

    _sync_integration_status(db, payload.bot_id, payload.status)
    return {"ok": True}


async def _send_whatsapp_message(bot_id: int, to: str, message: str) -> None:
    """Push a message to a number outside the normal request/reply cycle
    (e.g. the delayed auto-confirm below, where there's no inbound message
    to reply to). NOTE: this assumes whatsapp-service exposes a send route
    shaped like POST /session/{bot_id}/send {to, message} — check your
    whatsapp-service source and adjust the path/payload if it differs."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{WHATSAPP_SERVICE_URL}/session/{bot_id}/send",
                json={"to": to, "message": message},
                timeout=15,
            )
            resp.raise_for_status()
    except Exception as e:
        print(f"[whatsapp] failed to send confirmation to {to} (bot {bot_id}): {e}")


async def _finalize_order(bot_id: int, sender: str, port: int,
                           order_details: dict, cart_items: list) -> Optional[str]:
    """Calls /finalize and returns the confirmation text to send back on
    WhatsApp, or None if there was nothing to finalize or the call failed."""
    if not cart_items:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                bot_service_url(port, "/finalize"),
                json={
                    "session_id": f"whatsapp-{sender}",
                    "order_details": order_details,
                    "cart_items": cart_items,
                    "bot_id": bot_id,
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
    except Exception as e:
        print(f"[whatsapp] finalize failed for bot {bot_id} sender {sender}: {e}")
        return None
    return f"{result.get('message', 'Order confirmed!')} Total: Rs.{result.get('total', 0)}"


async def _auto_finalize_after_delay(bot_id: int, sender: str, port: int,
                                      state_key: tuple, token: str,
                                      order_details: dict, cart_items: list,
                                      delay: int = 60) -> None:
    """Equivalent of the web widget's JS countdown — waits, then finalizes
    the order itself and sends the confirmation over WhatsApp."""
    await asyncio.sleep(delay)

    # A newer message from this sender started a fresher timer (or the
    # order was already confirmed/superseded) — don't finalize a stale one.
    if _whatsapp_timer_tokens.get(state_key) != token:
        return

    confirm_text = await _finalize_order(bot_id, sender, port, order_details, cart_items)
    if confirm_text is None:
        return

    _whatsapp_timer_tokens.pop(state_key, None)
    _whatsapp_order_state.pop(state_key, None)
    await _send_whatsapp_message(bot_id, sender, confirm_text)


@router.post("/incoming")
async def handle_incoming_message(payload: IncomingMessage, db: Session = Depends(get_db)):
    """Called by whatsapp-service for every inbound WhatsApp message.

    Forwards to the SAME /chat endpoint your web widget calls (on whichever
    port that bot's category runs on), tagged channel="whatsapp". That /chat
    endpoint already logs the turn into conversations (see _log_turn in the
    bot's main.py) — so nothing needs to be saved here separately.
    """
    port = _get_bot_port(db, payload.bot_id)

    # Give each WhatsApp sender their own session id so bot.py's server-side
    # conversation history (sessions[sid]) doesn't collide with the web widget.
    session_id = f"whatsapp-{payload.sender}"
    state_key = (payload.bot_id, payload.sender)
    prior_state = _whatsapp_order_state.get(state_key, {})

    # Customer texted "confirm"/"ok"/etc. while a countdown is running —
    # finalize right now instead of making them wait out the 60s. /chat has
    # no branch for this state at all, so we short-circuit before reaching it.
    if state_key in _whatsapp_timer_tokens and _is_confirm_signal(payload.message):
        _whatsapp_timer_tokens.pop(state_key, None)  # cancel the pending delayed timer
        confirm_text = await _finalize_order(
            payload.bot_id, payload.sender, port,
            prior_state.get("order_details", {}), prior_state.get("cart_items", []),
        )
        _whatsapp_order_state.pop(state_key, None)
        return {
            "reply": confirm_text or "Sorry, couldn't confirm your order right now — please try again in a moment.",
            "images": [],
        }

    outgoing_message = payload.message or ""

    # WhatsApp transcript upload: the bot's own /chat only understands text,
    # so extract the PDF text here and hand it over as part of the message —
    # the FYP bot's system prompt already knows how to parse a raw transcript
    # (see the CAPSTONE PROJECT-I ELIGIBILITY RULES section in its prompt),
    # same as if someone pasted the transcript text into the web widget.
    if payload.file_base64:
        extracted = _extract_pdf_text(payload.file_base64)
        if extracted:
            outgoing_message = (
                f"{outgoing_message}\n\n[Attached transcript PDF — extracted text below]\n{extracted}"
            ).strip()
        else:
            outgoing_message = (
                outgoing_message
                or "I uploaded a transcript PDF, but its text couldn't be read automatically "
                   "(it may be a scanned image). Could you paste the transcript details as text instead?"
            )

    chat_payload = {
        "session_id": session_id,
        "message": outgoing_message,
        "channel": "whatsapp",
        "bot_id": payload.bot_id,  # the bot whose WhatsApp session received this
                                    # message — without this, /chat falls back
                                    # to its own .env BOT_ID for every sender
        "cart_items": prior_state.get("cart_items", []),
        "order_details": prior_state.get("order_details", {}),
        "awaiting_order_details": prior_state.get("awaiting_order_details", False),
        "current_field": prior_state.get("current_field"),
        "pending_cart": prior_state.get("pending_cart", []),
        "awaiting_confirmation": prior_state.get("awaiting_confirmation", False),
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                bot_service_url(port, "/chat"), json=chat_payload,
                timeout=60 if payload.file_base64 else 30
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[whatsapp] /incoming -> bot /chat failed: {e}")
        return {"reply": "Sorry, I'm having trouble replying right now — please try again in a moment."}

    # Persist whatever state /chat handed back so the next message from this
    # sender picks up the same cart / order-collection step.
    new_state = data.get("state", {}) or {}
    merged_state = {**prior_state, **new_state}
    _whatsapp_order_state[state_key] = {
        k: v for k, v in merged_state.items() if k in ORDER_STATE_FIELDS
    }

    # /chat signals the same "60s auto-confirm" state it gives the web
    # widget — but only the web widget has JS to act on it. Run the
    # equivalent countdown here so WhatsApp orders actually get finalized.
    if new_state.get("timer_active"):
        token = str(uuid.uuid4())
        _whatsapp_timer_tokens[state_key] = token
        asyncio.create_task(_auto_finalize_after_delay(
            payload.bot_id, payload.sender, port, state_key, token,
            _whatsapp_order_state[state_key].get("order_details", {}),
            _whatsapp_order_state[state_key].get("cart_items", []),
        ))

    # Different bot categories key their reply text differently — the
    # restaurant bot returns "message", UniBot returns "reply". Check both
    # so we don't silently send an empty WhatsApp message for either one.
    reply_text = data.get("message") or data.get("reply") or ""

    # Restaurant bot's "menu_items" replies include an `items` list with an
    # `img` field — either a full URL already, or a relative path like
    # "/images/burger.jpg" that only resolves against that bot's own
    # host:port (it mounts StaticFiles there). Turn those into absolute
    # URLs so Baileys can actually fetch and send them as WhatsApp images.
    MAX_IMAGES = 5  # avoid flooding a WhatsApp chat with dozens of images at once
    images = []
    for item in (data.get("items") or [])[:MAX_IMAGES]:
        img = item.get("img") or ""
        if not img:
            continue
        url = img if img.startswith("http") else bot_service_url(port, img)
        caption = item.get("name", "")
        if item.get("price") is not None:
            caption = f"{caption} — Rs.{item['price']}"
        images.append({"url": url, "caption": caption})

    return {"reply": reply_text, "images": images}
