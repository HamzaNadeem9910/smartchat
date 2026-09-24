from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Any
from datetime import datetime, date
from enum import Enum


# ─── Enums ───────────────────────────────────────────────────
class SubscriberPlanEnum(str, Enum):
    free     = "free"
    standard = "standard"
    premium  = "premium"

class PaymentStatusEnum(str, Enum):
    pending   = "pending"
    completed = "completed"
    failed    = "failed"
    refunded  = "refunded"

class PaymentMethodEnum(str, Enum):
    jazzcash  = "jazzcash"
    easypaisa = "easypaisa"
    bank      = "bank"
    card      = "card"
    manual    = "manual"

class SubscriberStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"

class ChatbotStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    training = "training"

class ChatbotCategoryEnum(str, Enum):
    university = "university"
    faculty = "faculty"
    fyp = "fyp"
    restaurant = "restaurant"
    general = "general"

class ConversationStatusEnum(str, Enum):
    active = "active"
    resolved = "resolved"
    escalated = "escalated"

class MessageRoleEnum(str, Enum):
    user = "user"
    bot = "bot"

class DocTypeEnum(str, Enum):
    pdf = "pdf"
    docx = "docx"
    txt = "txt"
    faq = "faq"
    website = "website"

class DocStatusEnum(str, Enum):
    pending = "pending"
    training = "training"
    trained = "trained"
    failed = "failed"

class FaqStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    training = "training"

class IntegrationTypeEnum(str, Enum):
    whatsapp = "whatsapp"
    email = "email"
    slack = "slack"
    website = "website"
    api = "api"

class IntegrationStatusEnum(str, Enum):
    connected = "connected"
    disconnected = "disconnected"
    pending = "pending"


# ─── Subscriber ──────────────────────────────────────────────
class SubscriberBase(BaseModel):
    name: str
    email: str
    plan: SubscriberPlanEnum = SubscriberPlanEnum.free
    status: SubscriberStatusEnum = SubscriberStatusEnum.active

class SubscriberCreate(SubscriberBase):
    password: str

class SubscriberLogin(BaseModel):
    email: str
    password: str

class SubscriberResponse(SubscriberBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type:   str
    user_id:      int
    email:        str
    plan:         Optional[str] = "free"
    name:         Optional[str] = None


# ─── Chatbot ─────────────────────────────────────────────────
class ChatbotCreate(BaseModel):
    name: str
    category: ChatbotCategoryEnum = ChatbotCategoryEnum.general
    status: ChatbotStatusEnum = ChatbotStatusEnum.inactive

class ChatbotUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[ChatbotCategoryEnum] = None
    status: Optional[ChatbotStatusEnum] = None
    conversations: Optional[int] = None
    accuracy: Optional[float] = None
    response_time: Optional[float] = None
    success_rate: Optional[float] = None

class ChatbotResponse(BaseModel):
    id: int
    subscriber_id: int
    name: str
    category: str
    status: str
    conversations: int
    accuracy: float
    response_time: float
    success_rate: float
    last_updated: datetime
    created_at: datetime
    class Config:
        from_attributes = True


# ─── Usage Stats ─────────────────────────────────────────────
class UsageStatsCreate(BaseModel):
    date: date
    messages_count: int = 0

class UsageStatsResponse(UsageStatsCreate):
    id: int
    chatbot_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class ChatbotDetailResponse(ChatbotResponse):
    usage_stats: List[UsageStatsResponse] = []


# ─── Conversation ────────────────────────────────────────────
class ConversationCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    topic: Optional[str] = None

class ConversationUpdate(BaseModel):
    status: Optional[ConversationStatusEnum] = None
    satisfaction: Optional[int] = None
    ended_at: Optional[datetime] = None

class ConversationResponse(BaseModel):
    id: int
    chatbot_id: int
    customer_name: Optional[str]
    customer_email: Optional[str]
    topic: Optional[str]
    status: str
    satisfaction: Optional[int]
    started_at: datetime
    ended_at: Optional[datetime]
    class Config:
        from_attributes = True


# ─── Conversation Message ────────────────────────────────────
class MessageCreate(BaseModel):
    role: MessageRoleEnum
    content: str

class MessageResponse(MessageCreate):
    id: int
    conversation_id: int
    created_at: datetime
    class Config:
        from_attributes = True


# ─── Knowledge Document ──────────────────────────────────────
class DocumentResponse(BaseModel):
    id: int
    chatbot_id: int
    name: str
    type: str
    file_path: Optional[str]
    source_url: Optional[str]
    size_label: Optional[str]
    status: str
    accuracy: Optional[float]
    training_progress: Optional[int]
    upload_date: Optional[date]
    pinecone_index: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ScrapeRequest(BaseModel):
    url: str


# ─── FAQ ─────────────────────────────────────────────────────
class FAQCreate(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    status: Optional[FaqStatusEnum] = None

class FAQResponse(FAQCreate):
    id: int
    chatbot_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ─── Integration ─────────────────────────────────────────────
class IntegrationResponse(BaseModel):
    id: int
    chatbot_id: int
    type: str
    status: str
    config_json: Optional[Any]
    connected_at: Optional[datetime]
    class Config:
        from_attributes = True


# ─── Customization ───────────────────────────────────────────
class CustomizationUpdate(BaseModel):
    theme: Optional[str] = None
    theme_color: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    button_color: Optional[str] = None
    button_shape: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    header_title: Optional[str] = None
    logo_url: Optional[str] = None
    position: Optional[str] = None
    welcome_message: Optional[str] = None

class CustomizationResponse(BaseModel):
    id: int
    chatbot_id: int
    theme: str
    theme_color: str
    background_color: str
    text_color: str
    button_color: str
    button_shape: str
    font_family: str
    font_size: int
    header_title: str
    logo_url: Optional[str]
    position: str
    welcome_message: Optional[str]
    class Config:
        from_attributes = True

# ─── Payment ──────────────────────────────────────────────────
class PaymentCreate(BaseModel):
    plan:            str                                    # standard | premium
    amount:          float
    payment_method:  PaymentMethodEnum = PaymentMethodEnum.manual
    transaction_id:  Optional[str]  = None
    notes:           Optional[str]  = None
    activate_trial:  bool           = False                 # activate 7-day free trial

class PaymentVerify(BaseModel):
    payment_id:      int
    transaction_id:  str
    status:          PaymentStatusEnum

class PaymentResponse(BaseModel):
    id:              int
    subscriber_id:   int
    plan:            str
    amount:          float
    currency:        str
    payment_method:  str
    transaction_id:  Optional[str]
    status:          str
    trial_used:      int
    trial_ends_at:   Optional[datetime]
    plan_starts_at:  datetime
    plan_ends_at:    Optional[datetime]
    notes:           Optional[str]
    created_at:      datetime
    class Config:
        from_attributes = True

class PlanLimits(BaseModel):
    plan:            str
    max_bots:        int
    max_messages:    int            # -1 = unlimited
    can_change_logo: bool
    smartchat_branding: bool
    price_pkr:       int
    trial_days:      int

class ActivePlanResponse(BaseModel):
    plan:            str
    status:          str            # active | trial | expired | free
    trial_ends_at:   Optional[datetime]
    plan_ends_at:    Optional[datetime]
    limits:          PlanLimits


# ─── Conversation Analysis ─────────────────────────────────────
class SentimentBreakdown(BaseModel):
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    overall: str

class TopicItem(BaseModel):
    topic: str
    count: int
    percentage: float

class FAQItem(BaseModel):
    question: str
    count: int
    sample_answer: Optional[str] = None

class ComplaintItem(BaseModel):
    text: str
    conversation_id: int
    customer_name: Optional[str] = None
    date: Optional[str] = None

class UnansweredItem(BaseModel):
    question: str
    count: int
    bot_reply: Optional[str] = None
    suggested_faq: Optional[str] = None

class RecommendationItem(BaseModel):
    title: str
    description: str
    priority: str = "medium"

class AnalysisReportResponse(BaseModel):
    generated_at: str
    days_range: int
    conversation_count: int
    message_count: int
    executive_summary: str
    sentiment: SentimentBreakdown
    top_topics: List[TopicItem]
    frequently_asked: List[FAQItem]
    complaints: List[ComplaintItem]
    unanswered_questions: List[UnansweredItem]
    recommendations: List[RecommendationItem]
    ai_available: bool
    cached: bool = False

class AskAIRequest(BaseModel):
    question: str
    days: int = 30

class AskAIResponse(BaseModel):
    answer: str
    ai_available: bool