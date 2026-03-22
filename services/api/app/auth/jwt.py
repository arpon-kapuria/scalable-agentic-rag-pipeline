from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from services.api.app.config import settings

# OAuth2 scheme tells Swagger UI where to send the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validates the JWT Token from the Authorization header.
    Decodes user info (ID, Role, Permissions).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decode Token
        # Verify signature using the Secret Key defined in Config
        # Token expiry check is handled automatically by PyJWT when decoding
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id: str | None = payload.get("sub")
        role: str = payload.get("role", "user")
        
        if user_id is None:
            raise credentials_exception

        # Return user context dict
        return {
            "id": user_id, 
            "role": role,
            "permissions": payload.get("permissions", [])
        }
        
    except InvalidTokenError:
        raise credentials_exception