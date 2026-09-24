"""
routers/admin.py
─────────────────────────────────────────────────────────────────
Admin-only endpoints for the SmartChat admin dashboard.

All routes are protected by a separate ADMIN_SECRET_KEY stored in
your .env (or config).  The dashboard logs in via POST /admin/login
and then sends:  Authorization: Bearer <admin_jwt>

Endpoints
─────────────────────────────────────────────────────────────────
POST  /admin/login                    → { access_token }
GET   /admin/me                       → token check
GET   /admin/subscribers              → all subscribers + plan info
PATCH /admin/subscribers/{id}         → update status
POST  /admin/subscribers/{id}/extend  → add 1 month to expiry

GET   /admin/payments                 → all payments + subscriber info
PATCH /admin/payments/{id}            → update status
POST  /admin/payments/{id}/confirm-extend → mark completed + extend sub

POST  /admin/notifications/send       → single email (stub — wire your SMTP)
POST  /admin/notifications/bulk       → bulk email  (stub — wire your SMTP)
POST  /admin/notifications/payment-email → payment email (stub)
"""

import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import Payment, PaymentStatus, Subscriber, SubscriberPlan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()

# ─────────────────────────────────────────────────────────────────
# Config — add ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_SECRET to your
# .env and config.py.  Fallbacks are shown here for quick testing.
# ─────────────────────────────────────────────────────────────────
ADMIN_EMAIL    = settings.ADMIN_EMAIL
ADMIN_PASSWORD = settings.ADMIN_PASSWORD
# Use a separate secret so admin tokens can't masquerade as user tokens
ADMIN_SECRET   = getattr(settings, "ADMIN_SECRET",   settings.SECRET_KEY + "_admin")
ADMIN_ALGO     = settings.ALGORITHM
ADMIN_TOKEN_EXPIRE_HOURS = 12

# ── Gmail SMTP config ─────────────────────────────────────────────
# Add these to your .env:
#   GMAIL_USER=your-sender@example.com
#   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (16-char Google App Password)
GMAIL_USER         = settings.GMAIL_USER
GMAIL_APP_PASSWORD = getattr(settings, "GMAIL_APP_PASSWORD", "")   # set in .env!
GMAIL_FROM_NAME    = "SmartChat Admin"


# ─────────────────────────────────────────────────────────────────
# Email helper
# ─────────────────────────────────────────────────────────────────

def _send_gmail(to_email: str, subject: str, html_body: str) -> None:
    """
    Send an HTML email via Gmail SMTP (TLS on port 587).
    Raises RuntimeError if sending fails so the endpoint can return a 500.
    """
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_APP_PASSWORD is not set in .env. "
            "Generate one at: Google Account → Security → 2-Step Verification → App Passwords"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{GMAIL_FROM_NAME} <{GMAIL_USER}>"
    msg["To"]      = to_email

    # Plain-text fallback
    plain = html_body.replace("<br>", "\n").replace("<br/>", "\n")
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        logger.info(f"[Gmail] Email sent → {to_email} | Subject: {subject}")
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "Gmail authentication failed. Make sure GMAIL_APP_PASSWORD is a valid "
            "16-character App Password (not your Gmail login password)."
        )
    except Exception as e:
        logger.error(f"[Gmail] Failed to send to {to_email}: {e}")
        raise RuntimeError(f"Failed to send email: {e}")


def _expiry_email_html(name: str, plan: str, days: int, expiry_date: str, custom_msg: str = "") -> str:
    """Returns a nicely formatted HTML expiry reminder email body."""
    urgency_color = "#ef4444" if days <= 7 else "#f59e0b" if days <= 14 else "#22c55e"
    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Segoe UI',Arial,sans-serif">
  <div style="max-width:560px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">
    <!-- Header -->
    <div style="background:#4f7ef8;padding:28px 32px">
      <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700">SmartChat</h1>
      <p style="margin:4px 0 0;color:rgba(255,255,255,.8);font-size:13px">Subscription Reminder</p>
    </div>
    <!-- Body -->
    <div style="padding:32px">
      <p style="font-size:15px;color:#111827;margin:0 0 16px">Hi <strong>{name}</strong>,</p>
      <p style="font-size:14px;color:#374151;margin:0 0 20px">
        {custom_msg if custom_msg else "This is a reminder that your SmartChat subscription is expiring soon."}
      </p>
      <!-- Days badge -->
      <div style="text-align:center;margin:24px 0">
        <div style="display:inline-block;background:{urgency_color};color:#fff;padding:12px 28px;border-radius:999px;font-size:18px;font-weight:700">
          {days} day{'s' if days != 1 else ''} remaining
        </div>
      </div>
      <!-- Details -->
      <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px">
        <tr style="background:#f9fafb">
          <td style="padding:10px 14px;color:#6b7280;border-radius:6px 0 0 6px">Plan</td>
          <td style="padding:10px 14px;font-weight:600;color:#111827;text-align:right">{plan.capitalize()}</td>
        </tr>
        <tr>
          <td style="padding:10px 14px;color:#6b7280">Expiry Date</td>
          <td style="padding:10px 14px;font-weight:600;color:#111827;text-align:right">{expiry_date}</td>
        </tr>
      </table>
      <p style="font-size:13px;color:#6b7280;margin:0">
        To renew, contact us or make a payment via JazzCash / EasyPaisa and send the transaction ID to 
        <a href="mailto:{GMAIL_USER}" style="color:#4f7ef8">{GMAIL_USER}</a>.
      </p>
    </div>
    <!-- Footer -->
    <div style="background:#f9fafb;padding:18px 32px;text-align:center;font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb">
      SmartChat &nbsp;·&nbsp; <a href="mailto:{GMAIL_USER}" style="color:#9ca3af">{GMAIL_USER}</a>
    </div>
  </div>
</body>
</html>"""


def _payment_email_html(name: str, amount: float, plan: str, txn_id: str, status: str, custom_msg: str = "") -> str:
    """Returns a payment status HTML email body."""
    status_color = "#22c55e" if status == "completed" else "#f59e0b" if status == "pending" else "#ef4444"
    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Segoe UI',Arial,sans-serif">
  <div style="max-width:560px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">
    <div style="background:#4f7ef8;padding:28px 32px">
      <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700">SmartChat</h1>
      <p style="margin:4px 0 0;color:rgba(255,255,255,.8);font-size:13px">Payment Update</p>
    </div>
    <div style="padding:32px">
      <p style="font-size:15px;color:#111827;margin:0 0 16px">Hi <strong>{name}</strong>,</p>
      <p style="font-size:14px;color:#374151;margin:0 0 20px">
        {custom_msg if custom_msg else f"Here is an update regarding your recent payment for the <strong>{plan.capitalize()}</strong> plan."}
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:24px">
        <tr style="background:#f9fafb">
          <td style="padding:10px 14px;color:#6b7280">Amount</td>
          <td style="padding:10px 14px;font-weight:700;color:#4f7ef8;text-align:right">₨{amount:,.0f}</td>
        </tr>
        <tr>
          <td style="padding:10px 14px;color:#6b7280">Plan</td>
          <td style="padding:10px 14px;font-weight:600;color:#111827;text-align:right">{plan.capitalize()}</td>
        </tr>
        <tr style="background:#f9fafb">
          <td style="padding:10px 14px;color:#6b7280">Transaction ID</td>
          <td style="padding:10px 14px;font-family:monospace;color:#111827;text-align:right">{txn_id or 'N/A'}</td>
        </tr>
        <tr>
          <td style="padding:10px 14px;color:#6b7280">Status</td>
          <td style="padding:10px 14px;text-align:right">
            <span style="background:{status_color};color:#fff;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600">{status.upper()}</span>
          </td>
        </tr>
      </table>
      <p style="font-size:13px;color:#6b7280;margin:0">
        If you have any questions, reply to this email or contact 
        <a href="mailto:{GMAIL_USER}" style="color:#4f7ef8">{GMAIL_USER}</a>.
      </p>
    </div>
    <div style="background:#f9fafb;padding:18px 32px;text-align:center;font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb">
      SmartChat &nbsp;·&nbsp; <a href="mailto:{GMAIL_USER}" style="color:#9ca3af">{GMAIL_USER}</a>
    </div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
# Pydantic schemas (inline — no need to touch schemas.py)
# ─────────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    email: str
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class SubStatusPatch(BaseModel):
    status: str   # active | inactive | expired

class ExtendRequest(BaseModel):
    months: int = 1
    plan:   Optional[str] = None   # if provided, also update plan on the payment record

class PayStatusPatch(BaseModel):
    status:         str                    # completed | pending | failed
    plan:           Optional[str]   = None # standard | premium | trial
    amount:         Optional[float] = None # 0 is valid (expired reset)
    transaction_id: Optional[str]   = None # null clears it on expiry

class ConfirmExtendRequest(BaseModel):
    subscriber_id: int

class SendNotifRequest(BaseModel):
    subscriber_id: int
    subject: str
    message: str

class BulkNotifRequest(BaseModel):
    subscriber_ids: List[int]
    message: str

class PaymentEmailRequest(BaseModel):
    payment_id: int
    message: str


# ─────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────

def _create_admin_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": email, "role": "admin", "exp": expire},
        ADMIN_SECRET,
        algorithm=ADMIN_ALGO,
    )


def _get_admin(authorization: Optional[str] = Header(None)):
    """Dependency — verifies the admin JWT in the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, ADMIN_SECRET, algorithms=[ADMIN_ALGO])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not an admin token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")


# ─────────────────────────────────────────────────────────────────
# POST /admin/login
# ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(body: AdminLoginRequest):
    """
    Authenticate admin credentials.
    Credentials are stored in .env (ADMIN_EMAIL / ADMIN_PASSWORD).
    Returns a short-lived JWT signed with ADMIN_SECRET.
    """
    if body.email != ADMIN_EMAIL or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    token = _create_admin_token(body.email)
    return {"access_token": token}


# ─────────────────────────────────────────────────────────────────
# GET /admin/me  — token health-check used by dashboard on reload
# ─────────────────────────────────────────────────────────────────

@router.get("/me")
def admin_me(admin=Depends(_get_admin)):
    return {"email": admin["sub"], "role": "admin"}


# ─────────────────────────────────────────────────────────────────
# GET /admin/subscribers
# Returns all subscribers joined with their latest completed payment
# ─────────────────────────────────────────────────────────────────

@router.get("/subscribers")
def list_subscribers(
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    """
    Returns every subscriber.  For each subscriber we also attach:
      - their latest completed payment plan & dates
      - trial info if on trial
    Maps directly to your `subscribers` + `payments` tables.
    """
    subscribers = db.query(Subscriber).order_by(Subscriber.id.desc()).all()
    now = datetime.utcnow()
    result = []

    for s in subscribers:
        # Latest completed payment
        completed_pay = (
            db.query(Payment)
            .filter(
                Payment.subscriber_id == s.id,
                Payment.status == PaymentStatus.completed,
            )
            .order_by(Payment.plan_starts_at.desc())
            .first()
        )

        # Active trial payment
        trial_pay = (
            db.query(Payment)
            .filter(
                Payment.subscriber_id == s.id,
                Payment.trial_used == 1,
                Payment.trial_ends_at > now,
            )
            .order_by(Payment.plan_starts_at.desc())
            .first()
        )

        plan_starts_at = None
        plan_ends_at   = None
        trial_ends_at  = None

        if completed_pay:
            plan_starts_at = completed_pay.plan_starts_at
            plan_ends_at   = completed_pay.plan_ends_at
        if trial_pay:
            trial_ends_at  = trial_pay.trial_ends_at
            if not plan_starts_at:
                plan_starts_at = trial_pay.plan_starts_at

        # Prefer plan from latest completed payment; fall back to subscriber's own plan field
        pay_plan     = completed_pay.plan if (completed_pay and completed_pay.plan) else None
        sub_plan     = s.plan.value if hasattr(s.plan, "value") else str(s.plan)
        resolved_plan = pay_plan or sub_plan

        result.append({
            "id"            : s.id,
            "name"          : s.name,
            "email"         : s.email,
            "phone"         : getattr(s, "phone", None),
            "plan"          : resolved_plan,
            "status"        : s.status.value if hasattr(s.status, "value") else str(s.status),
            "plan_starts_at": plan_starts_at.isoformat() if plan_starts_at else None,
            "plan_ends_at"  : plan_ends_at.isoformat()   if plan_ends_at   else None,
            "trial_ends_at" : trial_ends_at.isoformat()  if trial_ends_at  else None,
            "created_at"    : s.created_at.isoformat()   if getattr(s, "created_at", None) else None,
        })

    return result


# ─────────────────────────────────────────────────────────────────
# PATCH /admin/subscribers/{id}  — update status
# ─────────────────────────────────────────────────────────────────

@router.patch("/subscribers/{subscriber_id}")
def patch_subscriber(
    subscriber_id: int,
    body: SubStatusPatch,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    valid_statuses = {"active", "inactive", "expired", "suspended"}
    if body.status not in valid_statuses:
        raise HTTPException(400, f"status must be one of {valid_statuses}")

    sub = db.query(Subscriber).filter(Subscriber.id == subscriber_id).first()
    if not sub:
        raise HTTPException(404, "Subscriber not found")

    sub.status = body.status
    db.commit()
    db.refresh(sub)
    return {"id": sub.id, "status": body.status, "message": "Status updated"}


# ─────────────────────────────────────────────────────────────────
# POST /admin/subscribers/{id}/extend  — add N months to expiry
# ─────────────────────────────────────────────────────────────────

@router.post("/subscribers/{subscriber_id}/extend")
def extend_subscriber(
    subscriber_id: int,
    body: ExtendRequest,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    sub = db.query(Subscriber).filter(Subscriber.id == subscriber_id).first()
    if not sub:
        raise HTTPException(404, "Subscriber not found")

    # Find their latest completed payment to extend plan_ends_at
    pay = (
        db.query(Payment)
        .filter(
            Payment.subscriber_id == subscriber_id,
            Payment.status == PaymentStatus.completed,
        )
        .order_by(Payment.plan_starts_at.desc())
        .first()
    )

    now = datetime.utcnow()
    if pay:
        base = pay.plan_ends_at if (pay.plan_ends_at and pay.plan_ends_at > now) else now
        pay.plan_ends_at = base + timedelta(days=30 * body.months)
        if body.plan:
            pay.plan = body.plan
        new_expiry = pay.plan_ends_at
    else:
        # No payment — create a manual extension record
        new_expiry = now + timedelta(days=30 * body.months)
        manual_pay = Payment(
            subscriber_id  = subscriber_id,
            plan           = body.plan or (sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)),
            amount         = 0,
            currency       = "PKR",
            payment_method = "manual",
            transaction_id = None,
            status         = PaymentStatus.completed,
            trial_used     = 0,
            trial_ends_at  = None,
            plan_starts_at = now,
            plan_ends_at   = new_expiry,
            notes          = f"Manual admin extension — {body.months} month(s)",
        )
        db.add(manual_pay)

    # Update subscriber plan if provided
    if body.plan:
        try:
            sub.plan = body.plan
        except Exception:
            pass  # ignore if SubscriberPlan enum doesn't have this value

    # Reactivate if expired
    if str(sub.status) in ("expired", "inactive"):
        sub.status = "active"

    db.commit()
    return {
        "subscriber_id": subscriber_id,
        "new_expiry"   : new_expiry.isoformat(),
        "months_added" : body.months,
        "message"      : "Subscription extended",
    }


# ─────────────────────────────────────────────────────────────────
# GET /admin/payments
# Returns all payments joined with subscriber name + email
# ─────────────────────────────────────────────────────────────────

@router.get("/payments")
def list_payments(
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    """
    All rows from the `payments` table, newest first.
    Joins subscriber name & email so the dashboard doesn't need a
    second request.
    """
    payments = (
        db.query(Payment, Subscriber)
        .join(Subscriber, Payment.subscriber_id == Subscriber.id)
        .order_by(Payment.id.desc())
        .all()
    )

    result = []
    for pay, sub in payments:
        result.append({
            "id"              : pay.id,
            "subscriber_id"   : pay.subscriber_id,
            "subscriber_name" : sub.name,
            "subscriber_email": sub.email,
            "plan"            : pay.plan,
            "amount"          : float(pay.amount),
            "currency"        : pay.currency or "PKR",
            "payment_method"  : pay.payment_method,
            "transaction_id"  : pay.transaction_id,
            "status"          : pay.status.value if hasattr(pay.status, "value") else str(pay.status),
            "trial_used"      : pay.trial_used,
            "trial_ends_at"   : pay.trial_ends_at.isoformat()  if pay.trial_ends_at  else None,
            "plan_starts_at"  : pay.plan_starts_at.isoformat() if pay.plan_starts_at else None,
            "plan_ends_at"    : pay.plan_ends_at.isoformat()   if pay.plan_ends_at   else None,
            "created_at"      : pay.created_at.isoformat()     if getattr(pay, "created_at", None) else None,
        })
    return result


# ─────────────────────────────────────────────────────────────────
# PATCH /admin/payments/{id}  — update payment status
# ─────────────────────────────────────────────────────────────────

@router.patch("/payments/{payment_id}")
def patch_payment(
    payment_id: int,
    body: PayStatusPatch,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    valid = {"completed", "pending", "failed"}
    if body.status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")

    pay = db.query(Payment).filter(Payment.id == payment_id).first()
    if not pay:
        raise HTTPException(404, "Payment not found")

    pay.status = PaymentStatus(body.status)
    if body.plan is not None:
        pay.plan = body.plan
    if body.amount is not None:                        # 0 is valid (expired reset)
        pay.amount = body.amount
    if "transaction_id" in body.model_fields_set:      # only touch if explicitly sent
        pay.transaction_id = body.transaction_id       # None clears it, string sets it
    db.commit()
    return {"id": payment_id, "status": body.status, "plan": pay.plan, "amount": float(pay.amount), "transaction_id": pay.transaction_id, "message": "Payment updated"}


# ─────────────────────────────────────────────────────────────────
# POST /admin/payments/{id}/confirm-extend
# Marks payment completed AND extends subscriber +1 month
# ─────────────────────────────────────────────────────────────────

@router.post("/payments/{payment_id}/confirm-extend")
def confirm_and_extend(
    payment_id: int,
    body: ConfirmExtendRequest,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    pay = db.query(Payment).filter(Payment.id == payment_id).first()
    if not pay:
        raise HTTPException(404, "Payment not found")

    sub = db.query(Subscriber).filter(Subscriber.id == body.subscriber_id).first()
    if not sub:
        raise HTTPException(404, "Subscriber not found")

    now = datetime.utcnow()

    # Mark payment completed
    pay.status = PaymentStatus.completed

    # Set plan_ends_at (+30 days from now or from existing expiry)
    existing_ends = pay.plan_ends_at
    base = existing_ends if (existing_ends and existing_ends > now) else now
    pay.plan_ends_at = base + timedelta(days=30)

    # Activate subscriber plan
    sub.plan   = SubscriberPlan(pay.plan)
    sub.status = "active"

    db.commit()
    return {
        "payment_id"   : payment_id,
        "subscriber_id": body.subscriber_id,
        "new_expiry"   : pay.plan_ends_at.isoformat(),
        "message"      : "Payment confirmed and subscription extended by 1 month",
    }


# ─────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# These are stubs — wire your SMTP / SendGrid / Mailgun here.
# ─────────────────────────────────────────────────────────────────

@router.post("/notifications/send")
def send_notification(
    body: SendNotifRequest,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    """Send expiry reminder email to a single subscriber via Gmail SMTP."""
    sub = db.query(Subscriber).filter(Subscriber.id == body.subscriber_id).first()
    if not sub:
        raise HTTPException(404, "Subscriber not found")

    # Build expiry info for the HTML template
    latest_pay = (
        db.query(Payment)
        .filter(Payment.subscriber_id == sub.id, Payment.status == PaymentStatus.completed)
        .order_by(Payment.plan_starts_at.desc())
        .first()
    )
    from datetime import datetime as _dt
    now = _dt.utcnow()
    days_left = 0
    expiry_str = "N/A"
    plan_name  = sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)
    if latest_pay and latest_pay.plan_ends_at:
        diff = latest_pay.plan_ends_at - now
        days_left  = max(0, diff.days)
        expiry_str = latest_pay.plan_ends_at.strftime("%d %b %Y")

    html = _expiry_email_html(
        name=sub.name,
        plan=plan_name,
        days=days_left,
        expiry_date=expiry_str,
        custom_msg=body.message,
    )

    try:
        _send_gmail(to_email=sub.email, subject=body.subject, html_body=html)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "sent_to": sub.email,
        "subject": body.subject,
        "message": "Email sent successfully via Gmail",
    }


@router.post("/notifications/bulk")
def send_bulk_notifications(
    body: BulkNotifRequest,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    """Send bulk expiry reminder to multiple subscribers via Gmail SMTP."""
    subs = db.query(Subscriber).filter(Subscriber.id.in_(body.subscriber_ids)).all()
    from datetime import datetime as _dt
    now = _dt.utcnow()

    sent    = []
    failed  = []

    for sub in subs:
        # Resolve plan + expiry for each subscriber
        latest_pay = (
            db.query(Payment)
            .filter(Payment.subscriber_id == sub.id, Payment.status == PaymentStatus.completed)
            .order_by(Payment.plan_starts_at.desc())
            .first()
        )
        plan_name  = sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)
        days_left  = 0
        expiry_str = "N/A"
        if latest_pay and latest_pay.plan_ends_at:
            diff       = latest_pay.plan_ends_at - now
            days_left  = max(0, diff.days)
            expiry_str = latest_pay.plan_ends_at.strftime("%d %b %Y")

        subject = f"SmartChat Subscription Expiry Reminder — {days_left} Days Left"
        html    = _expiry_email_html(
            name=sub.name,
            plan=plan_name,
            days=days_left,
            expiry_date=expiry_str,
            custom_msg=body.message,
        )

        try:
            _send_gmail(to_email=sub.email, subject=subject, html_body=html)
            sent.append(sub.email)
            logger.info(f"[Bulk] Sent to {sub.email}")
        except RuntimeError as e:
            logger.error(f"[Bulk] Failed for {sub.email}: {e}")
            failed.append({"email": sub.email, "error": str(e)})

    return {
        "sent_count"  : len(sent),
        "failed_count": len(failed),
        "recipients"  : sent,
        "failed"      : failed,
        "message"     : f"{len(sent)} sent, {len(failed)} failed",
    }


@router.post("/notifications/payment-email")
def send_payment_email(
    body: PaymentEmailRequest,
    db: Session = Depends(get_db),
    admin=Depends(_get_admin),
):
    """Send payment status email to subscriber via Gmail SMTP."""
    pay = db.query(Payment).filter(Payment.id == body.payment_id).first()
    if not pay:
        raise HTTPException(404, "Payment not found")

    sub = db.query(Subscriber).filter(Subscriber.id == pay.subscriber_id).first()
    if not sub:
        raise HTTPException(404, "Subscriber not found")

    plan_name  = pay.plan or (sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan))
    pay_status = pay.status.value if hasattr(pay.status, "value") else str(pay.status)

    subject = f"SmartChat Payment {pay_status.capitalize()} — ₨{float(pay.amount):,.0f}"
    html    = _payment_email_html(
        name=sub.name,
        amount=float(pay.amount),
        plan=plan_name,
        txn_id=pay.transaction_id or "N/A",
        status=pay_status,
        custom_msg=body.message,
    )

    try:
        _send_gmail(to_email=sub.email, subject=subject, html_body=html)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "sent_to"   : sub.email,
        "payment_id": pay.id,
        "subject"   : subject,
        "message"   : "Payment email sent successfully via Gmail",
    }
