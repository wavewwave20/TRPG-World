"""인증 라우트."""

import hashlib
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Registration access code from environment variable
REGISTRATION_CODE = os.getenv("REGISTRATION_CODE", "")


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


class RegisterRequest(BaseModel):
    """Register request model."""

    username: str
    password: str
    access_code: str


class RegisterResponse(BaseModel):
    """Register response model."""

    user_id: int
    username: str
    message: str


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""

    user_id: int
    username: str
    message: str


@router.post("/register", response_model=RegisterResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.

    Args:
        request: Registration credentials with access code
        db: Database session

    Returns:
        RegisterResponse with user info

    Raises:
        HTTPException: If access code is invalid, username already exists, or validation fails
    """
    # Verify access code
    if request.access_code != REGISTRATION_CODE:
        raise HTTPException(status_code=403, detail="Invalid access code")

    # Validate username length
    if len(request.username) < 3 or len(request.username) > 50:
        raise HTTPException(status_code=400, detail="Username must be between 3 and 50 characters")

    # Validate password length
    if len(request.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    # Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user with hashed password
    hashed_password = hash_password(request.password)
    new_user = User(username=request.username, password=hashed_password)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RegisterResponse(user_id=new_user.id, username=new_user.username, message="Registration successful")


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login endpoint.

    Args:
        request: Login credentials
        db: Database session

    Returns:
        LoginResponse with user info

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Check password with hashing
    hashed_password = hash_password(request.password)
    if user.password != hashed_password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(user_id=user.id, username=user.username, message="Login successful")
