"""
Common schemas used across the application.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any


class ErrorDetail(BaseModel):
    """
    Generic error response schema for endpoints that don't have 
    a specific response model or need to return error details.
    """
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = {}
