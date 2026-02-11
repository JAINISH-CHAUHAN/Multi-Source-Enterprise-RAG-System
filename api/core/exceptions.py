"""
Custom exception hierarchy for the RAG application.

This module defines domain-specific exceptions that provide:
- Categorized error handling
- User-friendly error messages
- Detailed error context for logging
- Structured error codes for frontend consumption

Exception Hierarchy:
    BaseAppException
    ├── LLMException
    ├── EmbeddingException
    ├── VectorStoreException
    ├── IngestionException
    └── FileProcessingException
"""

from typing import Optional, Dict, Any


class BaseAppException(Exception):
    """
    Base exception for all application-specific errors.
    
    All custom exceptions inherit from this class to enable
    centralized error handling and consistent error responses.
    
    Attributes:
        error_code: Machine-readable error identifier (e.g., "LLM_API_ERROR")
        user_message: User-friendly error message for frontend display
        details: Additional context for logging and debugging
    """
    
    def __init__(
        self,
        error_code: str,
        user_message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.user_message = user_message
        self.details = details or {}
        super().__init__(user_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code,
            "error_message": self.user_message,
            "details": self.details
        }


class LLMException(BaseAppException):
    """
    Raised when LLM (Language Model) operations fail.
    
    Examples:
        - API key invalid/expired
        - Rate limit exceeded
        - Model unavailable
        - Timeout errors
        - Content policy violations
    """
    
    def __init__(
        self,
        user_message: str = "Language model service is temporarily unavailable",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "LLM_ERROR"
    ):
        super().__init__(
            error_code=error_code,
            user_message=user_message,
            details=details
        )


class EmbeddingException(BaseAppException):
    """
    Raised when embedding generation fails.
    
    Examples:
        - Embedding API connection failure
        - Token limit exceeded for embedding
        - Batch embedding partial failures
        - Invalid input format
    """
    
    def __init__(
        self,
        user_message: str = "Failed to generate embeddings for your content",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "EMBEDDING_ERROR"
    ):
        super().__init__(
            error_code=error_code,
            user_message=user_message,
            details=details
        )


class VectorStoreException(BaseAppException):
    """
    Raised when vector database operations fail.
    
    Examples:
        - ChromaDB connection failure
        - Persistence directory issues
        - Query/insert operation failures
        - Collection not found
    """
    
    def __init__(
        self,
        user_message: str = "Vector database operation failed",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "VECTOR_STORE_ERROR"
    ):
        super().__init__(
            error_code=error_code,
            user_message=user_message,
            details=details
        )


class IngestionException(BaseAppException):
    """
    Raised when document ingestion pipeline fails.
    
    Examples:
        - File processing failures
        - Chunking errors
        - Summarization failures
        - Batch processing errors
    """
    
    def __init__(
        self,
        user_message: str = "Document ingestion failed",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "INGESTION_ERROR"
    ):
        super().__init__(
            error_code=error_code,
            user_message=user_message,
            details=details
        )


class FileProcessingException(BaseAppException):
    """
    Raised when file I/O or document parsing fails.
    
    Examples:
        - Corrupted PDF/DOCX files
        - Unsupported file formats
        - File system permission errors
        - Disk space issues
    """
    
    def __init__(
        self,
        user_message: str = "Failed to process file",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "FILE_PROCESSING_ERROR"
    ):
        super().__init__(
            error_code=error_code,
            user_message=user_message,
            details=details
        )


class DatabaseException(BaseAppException):
    """
    Raised when database operations fail.
    
    Examples:
        - Connection failures
        - Query timeouts
        - Constraint violations
        - Transaction errors
    """
    
    def __init__(
        self,
        user_message: str = "Database operation failed",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "DATABASE_ERROR"
    ):
        super().__init__(
            error_code=error_code,
            user_message=user_message,
            details=details
        )
