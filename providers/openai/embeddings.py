from typing import List

from langchain_openai import OpenAIEmbeddings

from core.ai_interfaces import Embeddings
from api.core.exceptions import EmbeddingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIEmbeddingModel(Embeddings):
    """
    OpenAI implementation of the Embeddings interface.
    """

    def __init__(self, model: str):
        """
        model:
            OpenAI embedding model name
            (e.g. text-embedding-3-small)
        """
        self.model = model
        self.client = OpenAIEmbeddings(model=self.model)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents.
        """
        try:
            return self.client.embed_documents(texts)
        except Exception as e:
            logger.error(
                f"OpenAI embedding failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "num_texts": len(texts), "error_type": type(e).__name__}
            )
            raise EmbeddingException(
                user_message="Failed to generate embeddings. Please try again.",
                details={
                    "provider": "openai",
                    "model": self.model,
                    "num_texts": len(texts),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="EMBEDDING_OPENAI_ERROR"
            )

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query string.
        """
        try:
            return self.client.embed_query(text)
        except Exception as e:
            logger.error(
                f"OpenAI query embedding failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "error_type": type(e).__name__}
            )
            raise EmbeddingException(
                user_message="Failed to process your query. Please try again.",
                details={
                    "provider": "openai",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="EMBEDDING_OPENAI_QUERY_ERROR"
            )
