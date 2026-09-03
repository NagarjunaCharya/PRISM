from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from app.db.models import User, UserRole
from app.core.security import get_password_hash, verify_password
from app.core.config import settings

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, username: str, email: str, password: str, role: UserRole = UserRole.VIEWER) -> User:
    hashed_password = get_password_hash(password)
    db_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def is_account_locked(user: User) -> bool:
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False

def record_failed_login(db: Session, user: User):
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
    db.commit()

def reset_failed_login(db: Session, user: User):
    if user.failed_login_attempts > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

def authenticate_local_user(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user:
        return None
        
    if is_account_locked(user):
        return None
        
    if not verify_password(password, user.hashed_password):
        record_failed_login(db, user)
        return None
        
    reset_failed_login(db, user)
    return user
