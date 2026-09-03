from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel
import jwt

from app.db.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.services.user_service import authenticate_local_user, get_user_by_username, create_user
from app.services.ldap_service import ldap_service
from app.db.models import UserRole

router = APIRouter()

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 compatible token login, getting an access and refresh token.
    Tries LDAP authentication first, falls back to local DB.
    """
    username = form_data.username
    password = form_data.password
    
    # 1. Try LDAP Auth
    if ldap_service.authenticate(username, password):
        # LDAP Success - sync user to local DB if they don't exist
        user = get_user_by_username(db, username)
        if not user:
            role = ldap_service.get_user_roles(username)
            # Create a placeholder for LDAP users
            user = create_user(db, username=username, email=f"{username}@example.com", password="ldap_managed", role=role)
    else:
        # 2. Try Local DB Auth
        user = authenticate_local_user(db, username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password, or account locked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. Generate Tokens
    access_token = create_access_token(subject=user.username)
    refresh_token = create_refresh_token(subject=user.username)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
def refresh_token(
    request: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Use a refresh token to get a new access token.
    """
    try:
        payload = decode_token(request.refresh_token)
        username = payload.get("sub")
        token_type = payload.get("type")
        
        if token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
            
        user = get_user_by_username(db, username)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive or deleted")
            
        # Issue new tokens
        access_token = create_access_token(subject=user.username)
        new_refresh_token = create_refresh_token(subject=user.username)
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
