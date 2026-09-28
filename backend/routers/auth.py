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
            detail="Password is too long. Please use a shorter password."
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
        plan=user.plan,
        status=user.status
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
def login(credentials: SubscriberLogin, db: Session = Depends(get_db)):
    user = (
        db.query(Subscriber)
        .filter(Subscriber.email == credentials.email)
        .first()
    )

    if not user or not verify_password(
        credentials.password,
        user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if user.status == "suspended":
        raise HTTPException(
            status_code=403,
            detail="Account suspended"
        )

    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "plan": user.plan,
        "name": user.name,
    }


@router.post("/verify-token")
def verify_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")

        if email is None or user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        return {
            "valid": True,
            "email": email,
            "user_id": user_id
        }

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
