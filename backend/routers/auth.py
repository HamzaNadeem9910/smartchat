from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt

from database import get_db
from models import Subscriber
from schemas import SubscriberCreate, SubscriberLogin, SubscriberResponse, Token
from config import get_settings


router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password must be 72 bytes or less"
        )

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode("utf-8")

        if len(password_bytes) > 72:
            return False

        return bcrypt.checkpw(
            password_bytes,
            hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


@router.post("/signup", response_model=SubscriberResponse)
def signup(user: SubscriberCreate, db: Session = Depends(get_db)):
    # Enforce bcrypt's 72-byte password limit before any database work.
    # Byte length is used instead of character count because UTF-8
    # characters can occupy more than one byte.
    if len(user.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password must be 72 bytes or less"
        )

    existing_user = (
        db.query(Subscriber)
        .filter(Subscriber.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user.password)

    new_user = Subscriber(
        name=user.name,
        email=user.email,
        password=hashed_password,
