from typing import List, Any

from langchain_community.chat_models import ChatOllama

from core.ai_interfaces import LLM
from api.core.exceptions import LLMException
from api.core.logging import get_logger

logger = get_logger(__name__)


class OllamaLLM(LLM):
    """
    Ollama-based local LLM implementation.
    """

    def __init__(self, model: str, temperature: float = 0):
        """
        model:
            Ollama model name (e.g. llama3:8b-instruct-q4_K_M)
        """
        self.model = model
        self.temperature = temperature

        self.client = ChatOllama(
            model=self.model,
            temperature=self.temperature
        )

    def invoke(self, messages: List[Any]) -> str:
        try:
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(
                f"Ollama LLM invocation failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "error_type": type(e).__name__}
            )
            raise LLMException(
                user_message="Local AI model is unavailable. Please ensure Ollama is running.",
                details={
                    "provider": "ollama",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="LLM_OLLAMA_ERROR"
            )
