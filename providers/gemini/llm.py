from typing import List, Any

from langchain_google_genai import ChatGoogleGenerativeAI

from core.ai_interfaces import LLM
from api.core.exceptions import LLMException
from api.core.logging import get_logger

logger = get_logger(__name__)


class GeminiLLM(LLM):
    """
    Gemini implementation of the LLM interface.
    """

    def __init__(self, model: str, temperature: float = 0):
        """
        model:
            Gemini chat model name
            (e.g. gemini-1.5-pro, gemini-1.5-flash)
        """
        self.model = model
        self.temperature = temperature

        # API key is read implicitly from env:
        # GOOGLE_API_KEY
        self.client = ChatGoogleGenerativeAI(
            model=self.model,
            temperature=self.temperature
        )

    def invoke(self, messages: List[Any]) -> str:
        """
        Invoke Gemini chat model and return plain text.
        """
        try:
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(
                f"Gemini LLM invocation failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "error_type": type(e).__name__}
            )
            raise LLMException(
                user_message="AI model is temporarily unavailable. Please try again.",
                details={
                    "provider": "gemini",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="LLM_GEMINI_ERROR"
            )
