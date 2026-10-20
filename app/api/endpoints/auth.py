import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.postgres import get_db
from app.models.user_model import User
from app.schemas.user_sschema import UserCreate, OTPRequest, OTPVerify, UserResponse
from app.utils.jwt_handler import create_access_token, get_current_user

router = APIRouter(prefix="/v1/auth", tags=["Auth"])

# Simple in-memory token blacklist for logout (consider Redis/DB for production)
TOKEN_BLACKLIST: set[str] = set()

# ✅ Signup endpoint
@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        User.calling_code == user.calling_code,
        User.phone_number == user.phone_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        calling_code=user.calling_code,
        phone_number=user.phone_number,
        first_name=user.first_name,
        last_name=user.last_name,
        timezone=user.timezone
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=UserResponse)
def login(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        User.calling_code == user.calling_code,
        User.phone_number == user.phone_number
    ).first()
    if existing:
        return existing
    else:
        raise HTTPException(status_code=404, detail="User not found")

# ✅ Request OTP
@router.post("/request-otp")
def request_otp(req: OTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.calling_code == req.calling_code,
        User.phone_number == req.phone_number
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    db.commit()
    # TODO: send OTP via SMS (Twilio/Firebase). For now just return.
    return {"message": "OTP sent", "otp": otp}  # remove `otp` in prod

# ✅ Verify OTP & Login
@router.post("/verify-otp")
def verify_otp(req: OTPVerify, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.calling_code == req.calling_code,
        User.phone_number == req.phone_number
    ).first()
    if not user or user.otp_code != req.otp:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    # OTP matched → clear it
    user.otp_code = None
    db.commit()

    token = create_access_token({
        "user_id": user.id,
        "calling_code": user.calling_code,
        "phone_number": user.phone_number
    })
    return {"access_token": token, "token_type": "bearer"}

# ✅ Logout endpoint (JWT stateless)
@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: dict = Depends(get_current_user)):
    """
    Stateless logout for JWT-based auth.
    - Clients should discard the token locally.
    - Optionally, we track the token's jti or raw token for temporary revocation.
    """
    return {"message": "Logged out successfully"}