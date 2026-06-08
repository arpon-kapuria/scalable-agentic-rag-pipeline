from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import jwt
from jwt.exceptions import InvalidTokenError
from services.api.app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Token schema
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Token generation
def create_access_token(user_id: str, role: str = "user", permissions: list = []) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "permissions": permissions,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# Login endpoint
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    For production replace MOCK_USERS with real DB lookup.
    """
    MOCK_USERS = {
        "admin": {"password": "admin123", "role": "admin", "permissions": ["read", "write"]},
        "user":  {"password": "user123",  "role": "user",  "permissions": ["read"]},
    }
    user = MOCK_USERS.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        user_id=form_data.username,
        role=user["role"],
        permissions=user["permissions"]
    )
    return Token(access_token=token)

# Token validation
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        role: str = payload.get("role", "user")
        if user_id is None:
            raise credentials_exception
        return {
            "id": user_id,
            "role": role,
            "permissions": payload.get("permissions", [])
        }
    except InvalidTokenError:
        raise credentials_exception