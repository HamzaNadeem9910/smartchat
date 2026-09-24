import os
import json
import shutil
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Form, Query, Header
)
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Chatbot, Subscriber, ChatbotUsageStats,
    Conversation, ConversationMessage,
    KnowledgeDocument, FAQ, Integration, ChatbotCustomization,
    ConversationAnalysisSnapshot,
    IntegrationType, IntegrationStatus, DocType, DocStatus
)
from schemas import (
    ChatbotCreate, ChatbotResponse, ChatbotUpdate, ChatbotDetailResponse,
    UsageStatsResponse, UsageStatsCreate,
    ConversationCreate, ConversationUpdate, ConversationResponse,
    MessageCreate, MessageResponse,
    DocumentResponse, ScrapeRequest,
    FAQCreate, FAQUpdate, FAQResponse,
    IntegrationResponse,
    CustomizationUpdate, CustomizationResponse,
)
from config import get_settings

router = APIRouter(prefix="/chatbots", tags=["chatbots"])
settings = get_settings()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── OpenAI analysis config ──────────────────────────────────────
# Add OPENAI_API_KEY (required) and optionally OPENAI_MODEL to your .env / config.
AI_MODEL           = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
MAX_CONVOS_FOR_AI  = 15   # how many conversations get sent to OpenAI as context

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 20


# ─── Auth dependency ──────────────────────────────────────────
def get_current_subscriber(
    authorization: str = None,
    db: Session = Depends(get_db)
) -> Subscriber:
    """Decode JWT from Authorization header and return subscriber."""
    from fastapi import Header
    raise HTTPException(status_code=401, detail="Use dependency injection via Header")


def verify_token_dep(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Reusable token verifier — reads Bearer token from header."""
    return authorization


def get_user_from_token(token: str, db: Session) -> Subscriber:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(Subscriber).filter(Subscriber.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def extract_token_from_header(authorization: Optional[str], token_query: Optional[str] = None) -> str:
    """Extract Bearer token from Authorization header or query parameter (for backward compatibility)."""
    # Try Authorization header first
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        elif len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    # Fall back to query parameter for backward compatibility
    if token_query:
        return token_query
    
    raise HTTPException(status_code=401, detail="Missing authorization header or token parameter")


def verify_chatbot_owner(chatbot_id: int, user_id: int, db: Session) -> Chatbot:
    chatbot = db.query(Chatbot).filter(
        Chatbot.id == chatbot_id,
        Chatbot.subscriber_id == user_id
    ).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return chatbot


def ensure_customization(chatbot_id: int, db: Session) -> ChatbotCustomization:
    """Get or auto-create customization row for a chatbot."""
    cust = db.query(ChatbotCustomization).filter_by(chatbot_id=chatbot_id).first()
    if not cust:
        cust = ChatbotCustomization(chatbot_id=chatbot_id)
        db.add(cust)
        db.commit()
        db.refresh(cust)
    return cust


def ensure_integrations(chatbot_id: int, db: Session):
    """Auto-create all 5 integration rows if missing."""
    existing = {i.type.value for i in db.query(Integration).filter_by(chatbot_id=chatbot_id).all()}
    for t in IntegrationType:
        if t.value not in existing:
            db.add(Integration(chatbot_id=chatbot_id, type=t, status=IntegrationStatus.disconnected))
    db.commit()


# ═══════════════════════════════════════════════════════
# CHATBOT CRUD
# ═══════════════════════════════════════════════════════

@router.post("/", response_model=ChatbotResponse)
def create_chatbot(
    chatbot: ChatbotCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    new_bot = Chatbot(
        subscriber_id=user_id,
        name=chatbot.name,
        category=chatbot.category,
        status=chatbot.status,
    )
    db.add(new_bot)
    db.commit()
    db.refresh(new_bot)

    # Auto-create related rows
    ensure_customization(new_bot.id, db)
    ensure_integrations(new_bot.id, db)

    return new_bot


@router.get("/", response_model=List[ChatbotResponse])
def get_user_chatbots(
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(Chatbot).filter(Chatbot.subscriber_id == user_id).all()


@router.get("/{chatbot_id}", response_model=ChatbotDetailResponse)
def get_chatbot_detail(
    chatbot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    return verify_chatbot_owner(chatbot_id, user.id, db)


@router.put("/{chatbot_id}", response_model=ChatbotResponse)
def update_chatbot(
    chatbot_id: int,
    chatbot_update: ChatbotUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    chatbot = verify_chatbot_owner(chatbot_id, user.id, db)
    for field, value in chatbot_update.dict(exclude_unset=True).items():
        setattr(chatbot, field, value)
    db.commit()
    db.refresh(chatbot)
    return chatbot


@router.delete("/{chatbot_id}")
def delete_chatbot(
    chatbot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    chatbot = verify_chatbot_owner(chatbot_id, user.id, db)
    db.delete(chatbot)
    db.commit()
    return {"message": "Chatbot deleted successfully"}


# ═══════════════════════════════════════════════════════
# USAGE STATS
# ═══════════════════════════════════════════════════════

@router.get("/{chatbot_id}/stats", response_model=List[UsageStatsResponse])
def get_chatbot_stats(
    chatbot_id: int,
    user_id: int = Query(...),
    days: int = 7,
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    start = date.today() - timedelta(days=days)
    return db.query(ChatbotUsageStats).filter(
        ChatbotUsageStats.chatbot_id == chatbot_id,
        ChatbotUsageStats.date >= start
    ).all()


# ═══════════════════════════════════════════════════════
# CONVERSATIONS
# ═══════════════════════════════════════════════════════

@router.get("/{chatbot_id}/conversations", response_model=List[ConversationResponse])
def get_conversations(
    chatbot_id: int,
    user_id: int = Query(...),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    q = db.query(Conversation).filter(Conversation.chatbot_id == chatbot_id)
    if status:
        q = q.filter(Conversation.status == status)
    return q.order_by(Conversation.started_at.desc()).all()


@router.post("/{chatbot_id}/conversations", response_model=ConversationResponse)
def create_conversation(
    chatbot_id: int,
    body: ConversationCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    conv = Conversation(chatbot_id=chatbot_id, **body.dict())
    db.add(conv)
    # Increment chatbot conversations counter
    db.query(Chatbot).filter(Chatbot.id == chatbot_id).update(
        {Chatbot.conversations: Chatbot.conversations + 1}
    )
    db.commit()
    db.refresh(conv)
    return conv


@router.patch("/{chatbot_id}/conversations/{conv_id}", response_model=ConversationResponse)
def update_conversation(
    chatbot_id: int,
    conv_id: int,
    body: ConversationUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    conv = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.chatbot_id == chatbot_id
    ).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    for k, v in body.dict(exclude_unset=True).items():
        setattr(conv, k, v)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/{chatbot_id}/conversations/{conv_id}/messages", response_model=List[MessageResponse])
def get_messages(
    chatbot_id: int,
    conv_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    return db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conv_id
    ).order_by(ConversationMessage.created_at).all()


# ═══════════════════════════════════════════════════════
# KNOWLEDGE BASE — DOCUMENTS
# ═══════════════════════════════════════════════════════

@router.get("/{chatbot_id}/documents", response_model=List[DocumentResponse])
def get_documents(
    chatbot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    return db.query(KnowledgeDocument).filter(
        KnowledgeDocument.chatbot_id == chatbot_id
    ).order_by(KnowledgeDocument.created_at.desc()).all()


@router.post("/{chatbot_id}/documents/upload", response_model=DocumentResponse)
async def upload_document(
    chatbot_id: int,
    user_id: int = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read & size-check
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large. Max {MAX_FILE_SIZE_MB} MB.")

    # Save to disk
    unique_name = f"{uuid.uuid4().hex}{ext}"
    bot_dir = os.path.join(UPLOAD_DIR, str(chatbot_id))
    os.makedirs(bot_dir, exist_ok=True)
    file_path = os.path.join(bot_dir, unique_name)
    with open(file_path, "wb") as f:
        f.write(content)

    size_label = f"{round(size_mb, 1)} MB" if size_mb >= 1 else f"{round(len(content)/1024, 0):.0f} KB"
    doc_type = ext.lstrip(".")  # pdf / docx / txt

    doc = KnowledgeDocument(
        chatbot_id=chatbot_id,
        name=file.filename,
        type=doc_type,
        file_path=file_path,
        size_label=size_label,
        status=DocStatus.training,
        training_progress=0,
        upload_date=date.today(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # In production: trigger background training job here
    # background_tasks.add_task(train_document, doc.id)

    return doc


# POST /{chatbot_id}/documents/scrape is handled by crawlee_scrape.py router
# (registered in main.py as scrape_router) — do NOT add it here



@router.patch("/{chatbot_id}/documents/{doc_id}/progress")
def update_doc_progress(
    chatbot_id: int,
    doc_id: int,
    progress: int = Query(..., ge=0, le=100),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Called by background worker to update training progress."""
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.chatbot_id == chatbot_id
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.training_progress = progress
    if progress >= 100:
        doc.status = DocStatus.trained
        doc.accuracy = 90.0   # replace with real inference result
    db.commit()
    return {"progress": progress}


@router.delete("/{chatbot_id}/documents/{doc_id}")
def delete_document(
    chatbot_id: int,
    doc_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.chatbot_id == chatbot_id
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    # Remove file from disk
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


# ═══════════════════════════════════════════════════════
# KNOWLEDGE BASE — FAQs
# ═══════════════════════════════════════════════════════

@router.get("/{chatbot_id}/faqs", response_model=List[FAQResponse])
def get_faqs(
    chatbot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    return db.query(FAQ).filter(FAQ.chatbot_id == chatbot_id).order_by(FAQ.created_at.desc()).all()


@router.post("/{chatbot_id}/faqs", response_model=FAQResponse)
def create_faq(
    chatbot_id: int,
    body: FAQCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    faq = FAQ(chatbot_id=chatbot_id, **body.dict())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.put("/{chatbot_id}/faqs/{faq_id}", response_model=FAQResponse)
def update_faq(
    chatbot_id: int,
    faq_id: int,
    body: FAQUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    faq = db.query(FAQ).filter(FAQ.id == faq_id, FAQ.chatbot_id == chatbot_id).first()
    if not faq:
        raise HTTPException(404, "FAQ not found")
    for k, v in body.dict(exclude_unset=True).items():
        setattr(faq, k, v)
    db.commit()
    db.refresh(faq)
    return faq


@router.delete("/{chatbot_id}/faqs/{faq_id}")
def delete_faq(
    chatbot_id: int,
    faq_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    faq = db.query(FAQ).filter(FAQ.id == faq_id, FAQ.chatbot_id == chatbot_id).first()
    if not faq:
        raise HTTPException(404, "FAQ not found")
    db.delete(faq)
    db.commit()
    return {"message": "FAQ deleted"}


# ═══════════════════════════════════════════════════════
# INTEGRATIONS
# ═══════════════════════════════════════════════════════

@router.get("/{chatbot_id}/integrations", response_model=List[IntegrationResponse])
def get_integrations(
    chatbot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    ensure_integrations(chatbot_id, db)
    return db.query(Integration).filter(Integration.chatbot_id == chatbot_id).all()


@router.post("/{chatbot_id}/integrations/{int_type}/connect", response_model=IntegrationResponse)
def toggle_integration(
    chatbot_id: int,
    int_type: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    intg = db.query(Integration).filter(
        Integration.chatbot_id == chatbot_id,
        Integration.type == int_type
    ).first()
    if not intg:
        raise HTTPException(404, "Integration not found")

    if intg.status == IntegrationStatus.connected:
        intg.status = IntegrationStatus.disconnected
        intg.connected_at = None
    else:
        intg.status = IntegrationStatus.connected
        intg.connected_at = datetime.utcnow()

    db.commit()
    db.refresh(intg)
    return intg




# ─────────────────────────────────────────────────────────────
# BOT LOG TURN  (called by Models/universityBot/main.py etc.)
# No auth token required — bot posts internally using API key
# ─────────────────────────────────────────────────────────────

from pydantic import BaseModel as PydanticBase

class LogTurnBody(PydanticBase):
    conv_id:        Optional[int]  = None
    user_message:   str
    bot_reply:      str
    customer_name:  Optional[str]  = None
    customer_email: Optional[str]  = None
    topic:          Optional[str]  = None


@router.post("/{chatbot_id}/conversations/log_turn")
def log_turn(
    chatbot_id: int,
    body: LogTurnBody,
    db: Session = Depends(get_db),
):
    """
    Upsert a conversation + append user and bot messages.
    Called internally by each bot backend (no subscriber auth needed).
    Returns {"conv_id": <id>}.
    """
    from models import MessageRole

    if body.conv_id:
        conv = db.query(Conversation).filter(
            Conversation.id == chatbot_id,
            Conversation.chatbot_id == chatbot_id
        ).first()
        # just fetch by conv_id regardless of ownership check
        conv = db.query(Conversation).filter(
            Conversation.id == body.conv_id
        ).first()
    else:
        conv = None

    if not conv:
        conv = Conversation(
            chatbot_id     = chatbot_id,
            customer_name  = body.customer_name,
            customer_email = body.customer_email,
            topic          = body.topic or body.user_message[:80],
            status         = "active",
        )
        db.add(conv)
        # bump conversation counter on chatbot
        db.query(Chatbot).filter(Chatbot.id == chatbot_id).update(
            {Chatbot.conversations: Chatbot.conversations + 1}
        )
        db.flush()   # get conv.id without full commit

    # Append user message
    db.add(ConversationMessage(
        conversation_id = conv.id,
        role            = MessageRole.user,
        content         = body.user_message,
    ))
    # Append bot reply
    db.add(ConversationMessage(
        conversation_id = conv.id,
        role            = MessageRole.bot,
        content         = body.bot_reply,
    ))

    db.commit()
    db.refresh(conv)
    return {"conv_id": conv.id}


# ═══════════════════════════════════════════════════════
# CUSTOMIZATION
# ═══════════════════════════════════════════════════════

@router.get("/{chatbot_id}/customization", response_model=CustomizationResponse)
def get_customization(
    chatbot_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    return ensure_customization(chatbot_id, db)


@router.put("/{chatbot_id}/customization", response_model=CustomizationResponse)
def update_customization(
    chatbot_id: int,
    body: CustomizationUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)
    cust = ensure_customization(chatbot_id, db)
    for k, v in body.dict(exclude_unset=True).items():
        setattr(cust, k, v)
    db.commit()
    db.refresh(cust)
    return cust


# ═══════════════════════════════════════════════════════
# AI ANALYSIS
# ═══════════════════════════════════════════════════════

class AskAIChatMessage(BaseModel):
    role: str      # "user" | "assistant"
    content: str


class AskAIRequest(BaseModel):
    question: str
    chat_history: List[AskAIChatMessage] = []


def _build_conversation_texts(conversations: list) -> list:
    """Flatten Conversation + ConversationMessage rows into plain-text blocks for OpenAI."""
    conversation_texts = []
    for conv in conversations:
        # Ground truth verdict from _bot_resolved_conversation — the AI must
        # treat this as authoritative rather than re-deciding on its own,
        # so "Unanswered Questions" can't disagree with what the bot actually said.
        answered_verdict = "Answered" if _bot_resolved_conversation(conv) else "Unanswered"
        conv_text = f"Customer: {conv.customer_name}, Topic: {conv.topic}, Status: {conv.status}, Verdict: {answered_verdict}"
        if conv.satisfaction:
            conv_text += f", Satisfaction: {conv.satisfaction}/5"
        messages = []
        for msg in conv.messages:
            role = "Bot" if msg.role.value == 'bot' else "Customer"
            messages.append(f"{role}: {msg.content}")
        if messages:
            conv_text += "\n" + "\n".join(messages)
        conversation_texts.append(conv_text)
    return conversation_texts



# Fallback phrases that indicate the bot did NOT actually answer the
# customer's question (used to detect real resolution, not just status flags).
# Kept deliberately narrow — phrases like "please contact" or "not available"
# show up in plenty of genuine, helpful answers (e.g. a bot sharing office
# contact info), so only near-unambiguous "I don't know" style phrasing is
# used here to avoid marking real resolutions as unresolved.
_BOT_FALLBACK_PHRASES = (
    "i don't know", "i do not know",
    "i don't have that", "i do not have that",
    "i don't have any information", "i do not have any information",
    "i couldn't find", "i could not find",
    "i'm not sure", "i am not sure",
    "i cannot answer", "i can't answer",
    "i'm unable to help", "i am unable to help",
    "sorry, i don't", "sorry, i do not",
)


def _bot_resolved_conversation(conv) -> bool:
    """
    A conversation counts toward "resolved" if it's explicitly flagged that
    way, OR — regardless of the status field — the bot actually gave the
    customer a substantive answer (not a fallback/"I don't know" reply).
    Explicitly escalated conversations are never counted as resolved.
    """
    if conv.status == 'escalated':
        return False
    if conv.status == 'resolved':
        return True
    bot_messages = [
        m.content for m in conv.messages
        if m.role.value == 'bot' and m.content and m.content.strip()
    ]
    if not bot_messages:
        return False
    return any(
        not any(phrase in msg.lower() for phrase in _BOT_FALLBACK_PHRASES)
        for msg in bot_messages
    )


def _get_conversations_for_analysis(chatbot_id: int, days: int, db: Session):
    """
    Fetch conversations within the requested window. If none fall inside it —
    e.g. seed/demo data (or a slow week) older than `days` — fall back to the
    chatbot's entire history rather than reporting "0 conversations" just
    because of the date filter. Returns (conversations, used_all_time).
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    conversations = db.query(Conversation).filter(
        Conversation.chatbot_id == chatbot_id,
        Conversation.started_at >= start_date
    ).all()
    if conversations:
        return conversations, False

    all_time = (
        db.query(Conversation)
        .filter(Conversation.chatbot_id == chatbot_id)
        .all()
    )
    return all_time, bool(all_time)


@router.post("/{chatbot_id}/analyze")
def analyze_conversations(
    chatbot_id: int,
    user_id: int = Query(...),
    days: int = Query(30),
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Analyze conversation history with OpenAI and generate intelligent insights."""
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    chatbot = verify_chatbot_owner(chatbot_id, user.id, db)
    
    # Fetch conversations for the requested window, falling back to full
    # history if nothing falls inside it. Done before the cache check so we
    # can tell whether a cached snapshot is still representative of the
    # current data, not just whether it exists.
    conversations, used_all_time = _get_conversations_for_analysis(chatbot_id, days, db)
    
    # Check for cached analysis (within last 24 hours) — but ignore it if:
    #  - the caller explicitly asked for a fresh run (refresh=true, e.g. the
    #    user clicking "AI Analysis" again to re-analyze on demand),
    #  - it recorded 0 conversations (almost always stale, e.g. cached before
    #    new conversations came in), 
    #  - the live conversation count has since moved on from what's cached
    #    (new chats came in since it was generated), or
    #  - it's missing its executive summary (an earlier incomplete/broken
    #    generation that shouldn't get stuck being served for a full day).
    from datetime import datetime, timedelta
    cached = None if refresh else db.query(ConversationAnalysisSnapshot).filter(
        ConversationAnalysisSnapshot.chatbot_id == chatbot_id,
        ConversationAnalysisSnapshot.days_range == days,
        ConversationAnalysisSnapshot.generated_at >= datetime.utcnow() - timedelta(hours=24)
    ).first()
    
    if (
        cached
        and isinstance(cached.payload, dict)
        and cached.payload.get("overview", {}).get("total_conversations", 0) > 0
        and cached.payload.get("overview", {}).get("total_conversations") == len(conversations)
        and (cached.payload.get("executive_summary") or "").strip()
    ):
        return cached.payload
    
    if len(conversations) == 0:
        # Genuinely no conversations recorded, ever — don't cache this so the
        # very next real conversation triggers a fresh analysis.
        analysis_payload = {
            "chatbot_name": chatbot.name,
            "analysis_period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": "No conversations recorded yet. Start promoting your chatbot to generate data.",
            "top_topics": [],
            "faq": [],
            "complaints": [],
            "unanswered_questions": [],
            "ai_recommendations": [],
            "overview": {"total_conversations": 0}
        }
        return analysis_payload
    
    # Build conversation data for AI analysis
    conversation_texts = _build_conversation_texts(conversations)
    
    # Prepare data summary for OpenAI
    total_conversations = len(conversations)
    resolved_count = sum(1 for c in conversations if _bot_resolved_conversation(c))
    active_count = sum(1 for c in conversations if c.status == 'active')
    escalated_count = sum(1 for c in conversations if c.status == 'escalated')
    
    satisfaction_scores = [c.satisfaction for c in conversations if c.satisfaction]
    avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores) if satisfaction_scores else 0
    
    # Call OpenAI API for AI-powered analysis
    try:
        analysis_payload = generate_ai_analysis(
            chatbot.name,
            conversation_texts,
            total_conversations,
            resolved_count,
            escalated_count,
            avg_satisfaction,
            days
        )
    except Exception as e:
        # Fallback to basic analysis if OpenAI fails
        print(f"OpenAI analysis failed: {str(e)}")
        analysis_payload = generate_basic_analysis(
            chatbot.name,
            total_conversations,
            resolved_count,
            escalated_count,
            avg_satisfaction,
            conversations,
            days
        )
    
    analysis_payload["generated_at"] = datetime.utcnow().isoformat()
    analysis_payload["used_all_time"] = used_all_time
    
    # Cache the analysis
    snapshot = ConversationAnalysisSnapshot(
        chatbot_id=chatbot_id,
        days_range=days,
        payload=analysis_payload
    )
    db.add(snapshot)
    db.commit()
    
    return analysis_payload


# ─────────────────────────────────────────────────────────────────
# POST /chatbots/{id}/analyze/chat
# "Ask AI" — free-form Q&A grounded in the chatbot's own conversation
# history. Stateless: the frontend sends prior turns back each time.
# ─────────────────────────────────────────────────────────────────

@router.post("/{chatbot_id}/analyze/chat")
def ask_ai_about_conversations(
    chatbot_id: int,
    body: AskAIRequest,
    user_id: int = Query(...),
    days: int = Query(30),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Chat with your conversation data — answers are generated by OpenAI, grounded only in this chatbot's recent conversations."""
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    chatbot = verify_chatbot_owner(chatbot_id, user.id, db)

    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    conversations, _used_all_time = _get_conversations_for_analysis(chatbot_id, days, db)
    conversation_texts = _build_conversation_texts(conversations)

    try:
        answer = generate_ai_chat_answer(
            chatbot.name,
            conversation_texts,
            question,
            [m.dict() for m in body.chat_history],
        )
    except Exception as e:
        print(f"OpenAI chat failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Ask AI is temporarily unavailable — check that OPENAI_API_KEY is configured and try again.",
        )

    return {"answer": answer}


def generate_ai_analysis(
    chatbot_name: str,
    conversation_texts: list,
    total_conversations: int,
    resolved_count: int,
    escalated_count: int,
    avg_satisfaction: float,
    days: int
) -> dict:
    """Generate AI-powered analysis using OpenAI API."""
    if not settings.OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured")
    
    try:
        from openai import OpenAI
    except ImportError:
        raise Exception("OpenAI library not installed")
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Prepare conversation summary for AI
    conversation_sample = "\n\n---\n\n".join(conversation_texts[:MAX_CONVOS_FOR_AI]) or "(No conversations recorded in this period.)"
    
    prompt = f"""Analyze the following chatbot conversation data and provide a comprehensive AI-powered analysis in JSON format.

Chatbot Name: {chatbot_name}
Analysis Period: Last {days} days
Total Conversations: {total_conversations}
Resolved: {resolved_count}
Escalated: {escalated_count}
Average Satisfaction: {avg_satisfaction:.1f}/5

Sample Conversations:
{conversation_sample}

Please provide a JSON response with the following structure:
{{
    "executive_summary": "A 2-3 sentence high-level summary of bot performance and key findings, written in a warm, positive tone that highlights how the bot is helping customers — but grounded strictly in the real numbers above, never overstating results",
    "top_topics": [
        {{"topic": "topic name", "frequency": 0-100, "description": "brief description"}}
    ],
    "faq": [
        {{"question": "question", "answer": "suggested answer or bot response"}}
    ],
    "complaints": [
        {{"issue": "complaint summary", "frequency": "how often mentioned", "impact": "high/medium/low"}}
    ],
    "unanswered_questions": [
        {{"question": "question the bot doesn't have a good answer for yet", "frequency": "how often asked", "importance": "high/medium/low"}}
    ],
    "ai_recommendations": [
        {{"recommendation": "specific actionable recommendation", "priority": "high/medium/low", "expected_impact": "brief description of impact"}}
    ]
}}

Tone guidance: write for the bot's owner, not the end customer. Keep every number and fact accurate — never invent resolutions or satisfaction that the data doesn't support. Within that constraint, frame things positively and constructively: never say the bot "failed" or "couldn't resolve" a query; instead describe gaps as opportunities (e.g. "could expand its knowledge base to cover X" rather than "the bot failed to answer X"). Complaints and unanswered_questions should still be reported plainly and usefully — the goal is honest positivity, not hiding real gaps.

Each conversation above is tagged with "Verdict: Answered" or "Verdict: Unanswered" — this was determined programmatically from the bot's actual replies and is authoritative. Only include a question in "unanswered_questions" if it comes from a conversation tagged "Verdict: Unanswered". Never include a question from an "Verdict: Answered" conversation in unanswered_questions, even if the bot's answer seems incomplete to you — trust the tag over your own read of the wording.

Ensure all responses are accurate, actionable, and based on the conversation data provided."""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert chatbot analyst. Analyze conversation data and provide insights in the requested JSON format. Write with a positive, customer-satisfaction-focused tone — highlight what's working and describe gaps as opportunities rather than failures — while staying strictly accurate to the data provided. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        
        response_text = response.choices[0].message.content
        
        # Parse JSON response
        analysis = json.loads(response_text)
        
        return {
            "chatbot_name": chatbot_name,
            "analysis_period_days": days,
            "overview": {
                "total_conversations": total_conversations,
                "resolved": resolved_count,
                "escalated": escalated_count,
            },
            "executive_summary": analysis.get("executive_summary", ""),
            "top_topics": analysis.get("top_topics", []),
            "faq": analysis.get("faq", []),
            "complaints": analysis.get("complaints", []),
            "unanswered_questions": analysis.get("unanswered_questions", []),
            "ai_recommendations": analysis.get("ai_recommendations", [])
        }
    except Exception as e:
        print(f"Error parsing OpenAI response: {str(e)}")
        raise


def generate_ai_chat_answer(
    chatbot_name: str,
    conversation_texts: list,
    question: str,
    chat_history: list,
) -> str:
    """Answer a free-form question about a chatbot's conversation history, grounded only in the provided conversation data."""
    if not settings.OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured")

    try:
        from openai import OpenAI
    except ImportError:
        raise Exception("OpenAI library not installed")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    conversation_sample = "\n\n---\n\n".join(conversation_texts[:MAX_CONVOS_FOR_AI]) or "(No conversations recorded in this period.)"

    system_prompt = f"""You are a data analyst answering questions about the conversation history of the "{chatbot_name}" chatbot.
Only use the conversation data below to answer — never invent facts that aren't in it. If the data doesn't contain the answer, say so plainly rather than guessing.
Keep answers concise and specific, and reference real topics/customers from the data where it helps.

"Lead" / "leads" means the customer info captured in a conversation — name, email, phone, topic, and status. When asked for a lead, leads, or customer info, respond in structured Markdown: a "## " heading per customer (use their name, or "Lead" if unnamed), then their details as a bullet list (e.g. "- **Phone:** ..."), one customer block per lead. Only include fields that are actually present in the data — never invent a phone/email that isn't there.

For all other questions, plain sentences or a short bullet list are fine — reserve the heading-per-customer format for lead/customer-info requests.

Conversation data:
{conversation_sample}"""

    messages = [{"role": "system", "content": system_prompt}]
    for turn in chat_history[-10:]:  # keep the last few turns of context
        role, content = turn.get("role"), turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


def generate_basic_analysis(
    chatbot_name: str,
    total_conversations: int,
    resolved_count: int,
    escalated_count: int,
    avg_satisfaction: float,
    conversations: list,
    days: int
) -> dict:
    """Fallback basic analysis when OpenAI is unavailable."""
    resolution_rate = (resolved_count / max(total_conversations, 1)) * 100
    escalation_rate = (escalated_count / max(total_conversations, 1)) * 100
    
    executive_summary = f"Your {chatbot_name} chatbot handled {total_conversations} conversations in the last {days} days, successfully answering {resolution_rate:.0f}% of them."
    
    if avg_satisfaction > 0:
        if avg_satisfaction >= 4:
            executive_summary += f" Customers are highly satisfied, with an average rating of {avg_satisfaction:.1f}/5."
        else:
            executive_summary += f" Customers rated their experience {avg_satisfaction:.1f}/5 on average — there's room to grow that further."
    
    if escalation_rate > 20:
        executive_summary += f" {escalation_rate:.0f}% of conversations were escalated to a human for extra care."
    
    return {
        "chatbot_name": chatbot_name,
        "analysis_period_days": days,
        "overview": {
            "total_conversations": total_conversations,
            "resolved": resolved_count,
            "escalated": escalated_count,
        },
        "executive_summary": executive_summary,
        "top_topics": [{"topic": "Data analysis pending", "frequency": 0, "description": "Enable OpenAI for detailed topic analysis"}],
        "faq": [],
        "complaints": [],
        "unanswered_questions": [],
        "ai_recommendations": [
            {"recommendation": "Configure OpenAI API key for advanced AI-powered insights", "priority": "high", "expected_impact": "Unlock detailed conversation analysis"}
        ]
    }


@router.post("/{chatbot_id}/customization/logo")
async def upload_logo(
    chatbot_id: int,
    user_id: int = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    token = extract_token_from_header(authorization, token)
    user = get_user_from_token(token, db)
    verify_chatbot_owner(chatbot_id, user.id, db)

    allowed_img = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_img:
        raise HTTPException(400, "Invalid image format")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "Logo must be under 5 MB")

    logo_dir = os.path.join(UPLOAD_DIR, str(chatbot_id), "logos")
    os.makedirs(logo_dir, exist_ok=True)
    unique_name = f"logo_{uuid.uuid4().hex}{ext}"
    path = os.path.join(logo_dir, unique_name)
    with open(path, "wb") as f:
        f.write(content)

    # Public URL — adjust base URL to your deployment
    logo_url = f"/uploads/{chatbot_id}/logos/{unique_name}"
    cust = ensure_customization(chatbot_id, db)
    cust.logo_url = logo_url
    db.commit()

    return {"logo_url": logo_url}