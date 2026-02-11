# This file will:

# Import ChatOpenAI

# Implement the LLM interface from core/ai_interfaces.py

# Think of it as a plug.



# These files:

# Know they are OpenAI

# Know model names

# Know env vars

# But they expose only the interface, not OpenAI itself.

import os
from typing import List, Any

from langchain_openai import ChatOpenAI

from core.ai_interfaces import LLM
from api.core.exceptions import LLMException
from api.core.logging import get_logger

logger = get_logger(__name__)


class OpenAILLM(LLM):
    """
    OpenAI implementation of the LLM interface.
    """

    def __init__(self, model: str, temperature: float = 0):
        """
        model:
            OpenAI model name (e.g. gpt-4o-mini)
        """
        self.model = model
        self.temperature = temperature

        # API key is read implicitly by langchain from env:
        # OPENAI_API_KEY
        self.client = ChatOpenAI(
            model=self.model,
            temperature=self.temperature
        )

    def invoke(self, messages: List[Any]) -> str:
        """
        Invoke OpenAI chat model and return plain text.
        """
        try:
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(
                f"OpenAI LLM invocation failed: {str(e)}",
                exc_info=True,
                extra={"model": self.model, "error_type": type(e).__name__}
            )
            raise LLMException(
                user_message="AI model is temporarily unavailable. Please try again.",
                details={
                    "provider": "openai",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="LLM_OPENAI_ERROR"
            )
