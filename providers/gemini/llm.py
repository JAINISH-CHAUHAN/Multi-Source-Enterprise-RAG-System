from typing import List, Any

from langchain_google_genai import ChatGoogleGenerativeAI

from core.ai_interfaces import LLM


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
        response = self.client.invoke(messages)

        # LangChain returns an AIMessage
        return response.content
