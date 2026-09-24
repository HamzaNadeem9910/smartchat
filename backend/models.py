from sqlalchemy import (
    Column, Integer, String, Enum, Numeric, Text,
    DateTime, ForeignKey, Date, TIMESTAMP, JSON,
    func, SmallInteger, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base
import enum


# ─── Enums ───────────────────────────────────────────────────
class SubscriberStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"

class SubscriberPlan(str, enum.Enum):
    free     = "free"
    standard = "standard"
    premium  = "premium"

class PaymentStatus(str, enum.Enum):
    pending   = "pending"
    completed = "completed"
    failed    = "failed"
    refunded  = "refunded"

class PaymentMethod(str, enum.Enum):
    jazzcash    = "jazzcash"
    easypaisa   = "easypaisa"
    bank        = "bank"
    card        = "card"
    manual      = "manual"

class ChatbotStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    training = "training"

class ConversationStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"
    escalated = "escalated"

class MessageRole(str, enum.Enum):
    user = "user"
    bot = "bot"

class DocType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    txt = "txt"
    faq = "faq"
    website = "website"

class DocStatus(str, enum.Enum):
    pending = "pending"
    training = "training"
    trained = "trained"
    failed = "failed"

class FaqStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    training = "training"

class IntegrationType(str, enum.Enum):
    whatsapp = "whatsapp"
    email = "email"
    slack = "slack"
    website = "website"
    api = "api"

class IntegrationStatus(str, enum.Enum):
    connected = "connected"
    disconnected = "disconnected"
    pending = "pending"

class ChatTheme(str, enum.Enum):
    light = "light"
    dark = "dark"

class ButtonShape(str, enum.Enum):
    rounded = "rounded"
    square = "square"
    pill = "pill"

class WidgetPosition(str, enum.Enum):
    bottom_right = "bottom-right"
    bottom_left = "bottom-left"
    top_right = "top-right"
    top_left = "top-left"

class ChatbotCategory(str, enum.Enum):
    university = "university"
    faculty = "faculty"
    fyp = "fyp"
    restaurant = "restaurant"
    general = "general"


# ─── Models ──────────────────────────────────────────────────
class Subscriber(Base):
    __tablename__ = "subscribers"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    email      = Column(String(150), unique=True, nullable=False, index=True)
    password   = Column(String(255), nullable=False)
    plan       = Column(Enum(SubscriberPlan), default=SubscriberPlan.free)
    status     = Column(Enum(SubscriberStatus), default=SubscriberStatus.active)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    plan_expires_at = None   # resolved from payments table at runtime
    chatbots = relationship("Chatbot", back_populates="subscriber", cascade="all, delete-orphan")


class Chatbot(Base):
    __tablename__ = "chatbots"

    id            = Column(Integer, primary_key=True, index=True)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id", ondelete="CASCADE"), nullable=False)
    name          = Column(String(150), nullable=False)
    category      = Column(Enum(ChatbotCategory), default=ChatbotCategory.general)
    status        = Column(Enum(ChatbotStatus), default=ChatbotStatus.inactive)
    conversations = Column(Integer, default=0)
    accuracy      = Column(Numeric(5, 2), default=0.00)
    response_time = Column(Numeric(5, 2), default=0.00)
    success_rate  = Column(Numeric(5, 2), default=0.00)
    last_updated  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_at    = Column(TIMESTAMP, server_default=func.now())

    subscriber     = relationship("Subscriber", back_populates="chatbots")
    usage_stats    = relationship("ChatbotUsageStats", back_populates="chatbot", cascade="all, delete-orphan")
    conversations_ = relationship("Conversation", back_populates="chatbot", cascade="all, delete-orphan")
    documents      = relationship("KnowledgeDocument", back_populates="chatbot", cascade="all, delete-orphan")
    faqs           = relationship("FAQ", back_populates="chatbot", cascade="all, delete-orphan")
    integrations   = relationship("Integration", back_populates="chatbot", cascade="all, delete-orphan")
    customization  = relationship("ChatbotCustomization", back_populates="chatbot",
                                  uselist=False, cascade="all, delete-orphan")
    analysis_snapshots = relationship("ConversationAnalysisSnapshot", back_populates="chatbot",
                                       cascade="all, delete-orphan")
    whatsapp_session   = relationship("WhatsAppSession", back_populates="chatbot",
                                       uselist=False, cascade="all, delete-orphan")


class ChatbotUsageStats(Base):
    __tablename__ = "chatbot_usage_stats"

    id             = Column(Integer, primary_key=True, index=True)
    chatbot_id     = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    date           = Column(Date, nullable=False)
    messages_count = Column(Integer, default=0)
    created_at     = Column(TIMESTAMP, server_default=func.now())

    chatbot = relationship("Chatbot", back_populates="usage_stats")


class Conversation(Base):
    __tablename__ = "conversations"

    id             = Column(Integer, primary_key=True, index=True)
    chatbot_id     = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    customer_name  = Column(String(150))
    customer_email = Column(String(255))
    topic          = Column(String(255))
    status         = Column(Enum(ConversationStatus), default=ConversationStatus.active)
    satisfaction   = Column(SmallInteger)   # 1-5
    started_at     = Column(TIMESTAMP, server_default=func.now())
    ended_at       = Column(TIMESTAMP, nullable=True)

    chatbot  = relationship("Chatbot", back_populates="conversations_")
    messages = relationship("ConversationMessage", back_populates="conversation",
                            cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role            = Column(Enum(MessageRole), nullable=False)
    content         = Column(Text, nullable=False)
    created_at      = Column(TIMESTAMP, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id                = Column(Integer, primary_key=True, index=True)
    chatbot_id        = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    name              = Column(String(255), nullable=False)
    type              = Column(Enum(DocType), nullable=False)
    file_path         = Column(String(500))
    source_url        = Column(String(500))
    size_label        = Column(String(30))
    status            = Column(Enum(DocStatus), default=DocStatus.pending)
    accuracy          = Column(Numeric(5, 2))
    training_progress = Column(SmallInteger, default=0)
    upload_date       = Column(Date)
    pinecone_index    = Column(String(200), nullable=True)   # e.g. "user-13-bot-5"
    created_at        = Column(TIMESTAMP, server_default=func.now())
    updated_at        = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    chatbot = relationship("Chatbot", back_populates="documents")


class FAQ(Base):
    __tablename__ = "faqs"

    id         = Column(Integer, primary_key=True, index=True)
    chatbot_id = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    question   = Column(Text, nullable=False)
    answer     = Column(Text, nullable=False)
    category   = Column(String(100))
    status     = Column(Enum(FaqStatus), default=FaqStatus.active)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    chatbot = relationship("Chatbot", back_populates="faqs")


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("chatbot_id", "type", name="uq_chatbot_type"),)

    id           = Column(Integer, primary_key=True, index=True)
    chatbot_id   = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    type         = Column(Enum(IntegrationType), nullable=False)
    status       = Column(Enum(IntegrationStatus), default=IntegrationStatus.disconnected)
    config_json  = Column(JSON)
    connected_at = Column(TIMESTAMP, nullable=True)
    created_at   = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    chatbot = relationship("Chatbot", back_populates="integrations")


class ChatbotCustomization(Base):
    __tablename__ = "chatbot_customization"

    id               = Column(Integer, primary_key=True, index=True)
    chatbot_id       = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"),
                               nullable=False, unique=True)
    theme            = Column(Enum(ChatTheme), default=ChatTheme.light)
    theme_color      = Column(String(20), default="#4285F4")
    background_color = Column(String(20), default="#ffffff")
    text_color       = Column(String(20), default="#333333")
    button_color     = Column(String(20), default="#34A853")
    button_shape     = Column(Enum(ButtonShape), default=ButtonShape.rounded)
    font_family      = Column(String(100), default="Inter")
    font_size        = Column(SmallInteger, default=14)
    header_title     = Column(String(150), default="Chat Support")
    logo_url         = Column(String(500))
    position         = Column(Enum(WidgetPosition), default=WidgetPosition.bottom_right)
    welcome_message  = Column(Text, default="Hi! How can I help you today?")
    updated_at       = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    chatbot = relationship("Chatbot", back_populates="customization")

class ConversationAnalysisSnapshot(Base):
    __tablename__ = "conversation_analysis_snapshots"

    id           = Column(Integer, primary_key=True, index=True)
    chatbot_id   = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False)
    days_range   = Column(Integer, default=30)
    payload      = Column(JSON, nullable=False)
    generated_at = Column(TIMESTAMP, server_default=func.now())

    chatbot = relationship("Chatbot", back_populates="analysis_snapshots")


class Payment(Base):
    __tablename__ = "payments"

    id               = Column(Integer, primary_key=True, index=True)
    subscriber_id    = Column(Integer, ForeignKey("subscribers.id", ondelete="CASCADE"), nullable=False)
    plan             = Column(String(20), nullable=False)          # standard | premium
    amount           = Column(Numeric(10, 2), nullable=False)      # PKR
    currency         = Column(String(5), default="PKR")
    payment_method   = Column(Enum(PaymentMethod), default=PaymentMethod.manual)
    transaction_id   = Column(String(200), nullable=True)          # JazzCash/EasyPaisa TXN id
    status           = Column(Enum(PaymentStatus), default=PaymentStatus.pending)
    trial_used       = Column(Integer, default=0)                  # 1 if 7-day trial activated
    trial_ends_at    = Column(TIMESTAMP, nullable=True)
    plan_starts_at   = Column(TIMESTAMP, server_default=func.now())
    plan_ends_at     = Column(TIMESTAMP, nullable=True)            # null = lifetime / manual
    notes            = Column(Text, nullable=True)
    created_at       = Column(TIMESTAMP, server_default=func.now())
    updated_at       = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    subscriber = relationship("Subscriber", backref="payments")


class WhatsAppSession(Base):
    __tablename__ = "whatsapp_sessions"

    id           = Column(Integer, primary_key=True, index=True)
    bot_id       = Column(Integer, ForeignKey("chatbots.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    phone_number = Column(String(30), nullable=True)
    status       = Column(String(20), default="pending")  # pending | connected | disconnected
    created_at   = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    chatbot = relationship("Chatbot", back_populates="whatsapp_session")