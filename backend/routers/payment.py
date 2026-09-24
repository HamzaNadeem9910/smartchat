"""
routers/payment.py
Handles plan selection, payment recording, trial activation, and plan limit checks.

Plans:
  standard — 2 bots, 1000 msgs/month, 7-day free trial, SmartChat branding, Rs 4499
  premium  — 4 bots, unlimited msgs,  no trial,          no branding,        Rs 5999

Endpoints:
  GET  /payments/plans                    → list all plan details
  POST /payments/initiate                 → record a pending payment + optional trial
  POST /payments/verify                   → mark payment completed (after manual confirmation)
  GET  /payments/my-plan                  → current user's active plan + limits
  GET  /payments/history                  → all payments for current user
  GET  /payments/limits                   → just the limits (used by dashboard to gate features)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from database import get_db
from models import Subscriber, Payment, Chatbot, SubscriberPlan, PaymentStatus
from schemas import (
    PaymentCreate, PaymentVerify, PaymentResponse,
    PlanLimits, ActivePlanResponse,
)
from config import get_settings

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()

# ─────────────────────────────────────────────────────────────────
# Plan definitions
# ─────────────────────────────────────────────────────────────────

PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        plan="free",
        max_bots=1,
        max_messages=200,
        can_change_logo=False,
        smartchat_branding=True,
        price_pkr=0,
        trial_days=0,
    ),
    "standard": PlanLimits(
        plan="standard",
        max_bots=2,
        max_messages=1000,
        can_change_logo=False,
        smartchat_branding=True,
        price_pkr=4499,
        trial_days=7,
    ),
    "premium": PlanLimits(
        plan="premium",
        max_bots=4,
        max_messages=-1,          # unlimited
        can_change_logo=True,
        smartchat_branding=False,
        price_pkr=5999,
        trial_days=0,
    ),
}

# ─────────────────────────────────────────────────────────────────
# Auth helper — extract user from JWT in Authorization header
# ─────────────────────────────────────────────────────────────────

def _get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Subscriber:
    """Extract user from JWT in Authorization header or query param."""
    raw = None
    
    # Try Authorization header first (format: "Bearer <token>")
    if authorization and authorization.startswith("Bearer "):
        raw = authorization.split(" ", 1)[1]
    # Fall back to query parameter
    elif token:
        raw = token

    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(raw, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(Subscriber).filter(Subscriber.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ─────────────────────────────────────────────────────────────────
# Internal: resolve current plan status for a user
# ─────────────────────────────────────────────────────────────────

def _resolve_plan(user: Subscriber, db: Session) -> ActivePlanResponse:
    now = datetime.utcnow()

    # Get latest completed payment
    payment = (
        db.query(Payment)
        .filter(
            Payment.subscriber_id == user.id,
            Payment.status == PaymentStatus.completed,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )

    # Check if still in trial
    trial_payment = (
        db.query(Payment)
        .filter(
            Payment.subscriber_id == user.id,
            Payment.trial_used == 1,
            Payment.trial_ends_at > now,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )

    if trial_payment and (payment is None or payment.status != PaymentStatus.completed):
        # Active trial
        plan_name = trial_payment.plan
        return ActivePlanResponse(
            plan=plan_name,
            status="trial",
            trial_ends_at=trial_payment.trial_ends_at,
            plan_ends_at=None,
            limits=PLANS.get(plan_name, PLANS["free"]),
        )

    if payment:
        plan_name = payment.plan
        # Check expiry
        if payment.plan_ends_at and payment.plan_ends_at < now:
            # Expired — revert to free
            user.plan = SubscriberPlan.free
            db.commit()
            return ActivePlanResponse(
                plan="free",
                status="expired",
                trial_ends_at=None,
                plan_ends_at=payment.plan_ends_at,
                limits=PLANS["free"],
            )
        return ActivePlanResponse(
            plan=plan_name,
            status="active",
            trial_ends_at=None,
            plan_ends_at=payment.plan_ends_at,
            limits=PLANS.get(plan_name, PLANS["free"]),
        )

    # No payment at all — free plan
    return ActivePlanResponse(
        plan="free",
        status="free",
        trial_ends_at=None,
        plan_ends_at=None,
        limits=PLANS["free"],
    )

# ─────────────────────────────────────────────────────────────────
# GET /payments/plans — public, no auth needed
# ─────────────────────────────────────────────────────────────────

@router.get("/plans")
def list_plans():
    """Return all available plans and their limits."""
    return {"plans": list(PLANS.values())}

# ─────────────────────────────────────────────────────────────────
# POST /payments/initiate — user submits payment info
# ─────────────────────────────────────────────────────────────────

@router.post("/initiate", response_model=PaymentResponse)
def initiate_payment(
    body: PaymentCreate,
    user: Subscriber = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record a pending payment. Call this when user submits their
    JazzCash/EasyPaisa transaction ID or requests trial activation.

    - If activate_trial=True and plan=standard:
        Immediately activates 7-day trial (status = completed, trial_used = 1).
    - Otherwise: status = pending. Admin verifies and calls /verify.
    """
    if body.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    plan_limits = PLANS[body.plan]

    # Validate amount
    if not body.activate_trial and body.amount < plan_limits.price_pkr:
        raise HTTPException(
            status_code=400,
            detail=f"Amount Rs {body.amount} is less than plan price Rs {plan_limits.price_pkr}",
        )

    now = datetime.utcnow()
    trial_ends = None
    status = PaymentStatus.pending

    # Standard plan supports 7-day trial
    if body.activate_trial and body.plan == "standard" and plan_limits.trial_days > 0:
        # Check if user already used trial for this plan
        used = db.query(Payment).filter(
            Payment.subscriber_id == user.id,
            Payment.plan == body.plan,
            Payment.trial_used == 1,
        ).first()
        if used:
            raise HTTPException(status_code=400, detail="Free trial already used for this plan.")
        trial_ends = now + timedelta(days=plan_limits.trial_days)
        status = PaymentStatus.completed   # trial activates immediately
        body.amount = 0

    payment = Payment(
        subscriber_id  = user.id,
        plan           = body.plan,
        amount         = body.amount,
        currency       = "PKR",
        payment_method = body.payment_method,
        transaction_id = body.transaction_id,
        status         = status,
        trial_used     = 1 if body.activate_trial else 0,
        trial_ends_at  = trial_ends,
        plan_starts_at = now,
        plan_ends_at   = None,    # admin sets this after verification
        notes          = body.notes,
    )
    db.add(payment)

    # If trial: update subscriber plan immediately
    if body.activate_trial:
        user.plan = SubscriberPlan(body.plan)

    db.commit()
    db.refresh(payment)
    return payment

# ─────────────────────────────────────────────────────────────────
# POST /payments/verify — admin verifies a pending payment
# ─────────────────────────────────────────────────────────────────

@router.post("/verify", response_model=PaymentResponse)
def verify_payment(
    body: PaymentVerify,
    user_id: int = Query(...),
    token: str   = Query(...),
    db: Session  = Depends(get_db),
):
    """
    Admin endpoint — marks a pending payment as completed and activates the plan.
    Protected by token query param (same pattern as rest of SmartChat backend).
    """
    # Verify admin token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    payment = db.query(Payment).filter(Payment.id == body.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment.status         = PaymentStatus.completed
    payment.transaction_id = body.transaction_id
    payment.plan_ends_at   = datetime.utcnow() + timedelta(days=30)  # 1 month

    # Activate subscriber plan
    sub = db.query(Subscriber).filter(Subscriber.id == payment.subscriber_id).first()
    if sub:
        sub.plan = SubscriberPlan(payment.plan)

    db.commit()
    db.refresh(payment)
    return payment

# ─────────────────────────────────────────────────────────────────
# GET /payments/my-plan
# ─────────────────────────────────────────────────────────────────

@router.get("/my-plan", response_model=ActivePlanResponse)
def my_plan(
    user: Subscriber = Depends(_get_current_user),
    db: Session      = Depends(get_db),
):
    """Returns current user's active plan, status, and limits."""
    return _resolve_plan(user, db)

# ─────────────────────────────────────────────────────────────────
# GET /payments/limits — used by dashboard to gate features
# ─────────────────────────────────────────────────────────────────

@router.get("/limits")
def get_limits(
    user: Subscriber = Depends(_get_current_user),
    db: Session      = Depends(get_db),
):
    """
    Returns what the current user is allowed to do.
    Used by frontend to show/hide logo upload, branding badge, bot creation button.
    """
    plan_info  = _resolve_plan(user, db)
    bot_count  = db.query(Chatbot).filter(Chatbot.subscriber_id == user.id).count()
    limits     = plan_info.limits
    return {
        "plan":               plan_info.plan,
        "status":             plan_info.status,
        "trial_ends_at":      plan_info.trial_ends_at,
        "plan_ends_at":       plan_info.plan_ends_at,
        "max_bots":           limits.max_bots,
        "current_bots":       bot_count,
        "can_create_bot":     bot_count < limits.max_bots,
        "max_messages":       limits.max_messages,
        "can_change_logo":    limits.can_change_logo,
        "smartchat_branding": limits.smartchat_branding,
        "price_pkr":          limits.price_pkr,
    }

# ─────────────────────────────────────────────────────────────────
# GET /payments/history
# ─────────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[PaymentResponse])
def payment_history(
    user: Subscriber = Depends(_get_current_user),
    db: Session      = Depends(get_db),
):
    """All payments for the current user, newest first."""
    return (
        db.query(Payment)
        .filter(Payment.subscriber_id == user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
