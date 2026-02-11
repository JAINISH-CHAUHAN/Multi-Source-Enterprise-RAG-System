from pydantic import BaseModel, EmailStr
from typing import Optional

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    organization_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
    # Error handling fields (populated only on failure)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

class LogoutResponse(BaseModel):
    message: str
    
    # Error handling fields (populated only on failure)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
