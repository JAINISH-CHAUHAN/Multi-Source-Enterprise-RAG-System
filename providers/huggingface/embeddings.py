from typing import List

from langchain_community.embeddings import HuggingFaceEmbeddings

from core.ai_interfaces import Embeddings
from api.core.exceptions import EmbeddingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class HFEmbeddingModel(Embeddings):
    """
    HuggingFace / Sentence-Transformers embedding implementation.
    """

    def __init__(self, model: str):
        """
        model:
            e.g. sentence-transformers/all-MiniLM-L6-v2
        """
        self.model = model
        self.client = HuggingFaceEmbeddings(
            model_name=self.model
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            return self.client.embed_documents(texts)
        except Exception as e:
            logger.error(
                f"HuggingFace embedding failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "num_texts": len(texts), "error_type": type(e).__name__}
            )
            raise EmbeddingException(
                user_message="Failed to generate embeddings. Please try again.",
                details={
                    "provider": "huggingface",
                    "model": self.model,
                    "num_texts": len(texts),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="EMBEDDING_HUGGINGFACE_ERROR"
            )

    def embed_query(self, text: str) -> List[float]:
        try:
            return self.client.embed_query(text)
        except Exception as e:
            logger.error(
                f"HuggingFace query embedding failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "error_type": type(e).__name__}
            )
            raise EmbeddingException(
                user_message="Failed to process your query. Please try again.",
                details={
                    "provider": "huggingface",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="EMBEDDING_HUGGINGFACE_QUERY_ERROR"
            )
