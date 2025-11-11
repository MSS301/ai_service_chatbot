"""
Authentication utilities for AI Service Chatbot
Reads user information from headers injected by API Gateway
"""
from typing import Optional
from fastapi import Header, HTTPException, Depends
from app.core.logger import get_logger

logger = get_logger(__name__)


class UserInfo:
    """User information extracted from API Gateway headers"""
    def __init__(self, user_id: str, email: Optional[str] = None):
        self.user_id = user_id
        self.email = email
    
    def __repr__(self):
        return f"UserInfo(user_id={self.user_id}, email={self.email})"


async def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> UserInfo:
    """
    FastAPI dependency to get current user from X-User-Id header injected by API Gateway
    
    API Gateway validates JWT token and injects X-User-Id header before forwarding request.
    This dependency reads that header to get the authenticated user ID.
    
    Usage:
        @router.get("/protected")
        def protected_route(user: UserInfo = Depends(get_current_user)):
            return {"user_id": user.user_id}
    
    Args:
        x_user_id: User ID from X-User-Id header (injected by API Gateway)
        authorization: Authorization header (for logging/debugging, not validated here)
        
    Returns:
        UserInfo object with user information
        
    Raises:
        HTTPException: If X-User-Id header is missing (401 Unauthorized)
    """
    if not x_user_id:
        logger.warning("X-User-Id header missing - request may not have passed through API Gateway")
        raise HTTPException(
            status_code=401,
            detail="Missing X-User-Id header. Request must go through API Gateway with valid JWT token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract email from Authorization header if available (for logging)
    email = None
    if authorization and authorization.startswith("Bearer "):
        # Note: We don't validate JWT here - API Gateway already did that
        # This is just for extracting info if needed
        pass
    
    user_info = UserInfo(user_id=x_user_id, email=email)
    logger.debug(f"Authenticated user from header: {user_info.user_id}")
    
    return user_info


async def get_optional_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
) -> Optional[UserInfo]:
    """
    FastAPI dependency to optionally get current user (for endpoints that work with or without auth)
    
    Usage:
        @router.get("/public-or-authenticated")
        def flexible_route(user: Optional[UserInfo] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.user_id}"}
            return {"message": "Hello anonymous"}
    
    Args:
        x_user_id: User ID from X-User-Id header (optional)
        
    Returns:
        UserInfo if X-User-Id header is present, None otherwise
    """
    if not x_user_id:
        return None
    
    return UserInfo(user_id=x_user_id)

