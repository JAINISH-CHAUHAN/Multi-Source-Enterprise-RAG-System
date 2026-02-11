from typing import List

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from core.ai_interfaces import Embeddings
from api.core.exceptions import EmbeddingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class GeminiEmbeddingModel(Embeddings):
    """
    Gemini implementation of the Embeddings interface.
    """

    def __init__(self, model: str):
        """
        model:
            Gemini embedding model name
            (e.g. models/embedding-001)
        """
        self.model = model

        # API key is read implicitly from env:
        # GOOGLE_API_KEY
        self.client = GoogleGenerativeAIEmbeddings(
            model=self.model
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents.
        """
        try:
            return self.client.embed_documents(texts)
        except Exception as e:
            logger.error(
                f"Gemini embedding failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "num_texts": len(texts), "error_type": type(e).__name__}
            )
            raise EmbeddingException(
                user_message="Failed to generate embeddings. Please try again.",
                details={
                    "provider": "gemini",
                    "model": self.model,
                    "num_texts": len(texts),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="EMBEDDING_GEMINI_ERROR"
            )

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query string.
        """
        try:
            return self.client.embed_query(text)
        except Exception as e:
            logger.error(
                f"Gemini query embedding failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "error_type": type(e).__name__}
            )
            raise EmbeddingException(
                user_message="Failed to process your query. Please try again.",
                details={
                    "provider": "gemini",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="EMBEDDING_GEMINI_QUERY_ERROR"
            )
