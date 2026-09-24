"""
WhatsApp integration router for SmartChat.

Copy this file to backend/routers/whatsapp.py, then wire it into main.py:

    from routers import whatsapp
    app.include_router(whatsapp.router)

Adjust the chatbot-pipeline import/call in `handle_incoming_message` below to
match your actual per-category bot logic.
"""

import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import WhatsAppSession, Integration, IntegrationType, IntegrationStatus
# from your_chatbot_module import run_chatbot_pipeline   # <-- your existing chat logic
# from your_db_module import save_message                 # <-- your existing message-saving helper

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:4001")


class IncomingMessage(BaseModel):
    bot_id: int
    sender: str
    message: str


class StatusUpdate(BaseModel):
    bot_id: int
    status: str
    phone_number: Optional[str] = None


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


@router.post("/incoming")
async def handle_incoming_message(payload: IncomingMessage, db: Session = Depends(get_db)):
    """Called by whatsapp-service for every inbound WhatsApp message.
    Runs the SAME pipeline your web widget uses, just tagged with channel='whatsapp'."""

    # TODO: replace this stub with your actual chatbot pipeline call, e.g.:
    # reply_text = await run_chatbot_pipeline(
    #     bot_id=payload.bot_id, user_message=payload.message, channel="whatsapp"
    # )
    reply_text = f"(stub reply) You said: {payload.message}"

    # TODO: persist to your conversations/messages tables with channel="whatsapp", e.g.:
    # save_message(db, bot_id=payload.bot_id, sender=payload.sender, text=payload.message, channel="whatsapp")
    # save_message(db, bot_id=payload.bot_id, sender="bot", text=reply_text, channel="whatsapp")

    return {"reply": reply_text}