from typing import List

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from core.ai_interfaces import Embeddings


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
        return self.client.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query string.
        """
        return self.client.embed_query(text)
