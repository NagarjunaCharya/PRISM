from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any

from app.db.database import get_db
from app.db.models import User, UserRole
from app.api.dependencies import get_current_user, RoleChecker

router = APIRouter()

@router.get("/me")
def read_user_me(current_user: User = Depends(get_current_user)) -> Any:
    """
    Get current user profile.
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active
    }

@router.post("/admin-only")
def admin_only_action(
    current_user: User = Depends(RoleChecker([UserRole.ADMIN]))
) -> Any:
    """
    An endpoint that requires ADMIN privileges.
    """
    return {"message": "You have administrative access"}

@router.post("/safety-manager-action")
def manager_action(
    current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.SAFETY_MANAGER]))
) -> Any:
    """
    An endpoint that requires SAFETY_MANAGER or ADMIN privileges.
    """
    return {"message": "You can perform safety management actions"}
