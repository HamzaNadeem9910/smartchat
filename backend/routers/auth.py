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

        email = payload.get("sub")
        user_id = payload.get("user_id")

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
