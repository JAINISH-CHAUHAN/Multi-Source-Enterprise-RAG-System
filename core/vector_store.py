# This file owns everything related to DB lifecycle.
import os
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document

from core.ai_factory import get_embeddings
from api.core.exceptions import VectorStoreException, EmbeddingException
from api.core.logging import get_logger

logger = get_logger(__name__)


class VectorStoreManager:
    """
    Manages the lifecycle of the vector store (ChromaDB).

    Responsibilities:
    - Create or load an existing vector store
    - Add documents incrementally
    - Persist the store
    """

    def __init__(self, persist_directory: str = "chroma_db"):
        self.persist_directory = persist_directory
        
        try:
            self.embedding_model = get_embeddings("default")
        except Exception as e:
            logger.error(
                f"Failed to initialize embedding model: {str(e)}",
                exc_info=True,
                extra={"persist_directory": persist_directory, "error_type": type(e).__name__}
            )
            raise VectorStoreException(
                user_message="Failed to initialize vector store. Embedding service unavailable.",
                details={
                    "persist_directory": persist_directory,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="VECTOR_STORE_INIT_ERROR"
            )

        self._db = None

    def load_or_create(self) -> Chroma:
        """
        Load an existing vector store if it exists,
        otherwise create a new one.
        """
        if self._db is not None:
            return self._db

        try:
            if os.path.exists(self.persist_directory):
                logger.info(f"Loading existing vector store from {self.persist_directory}")
                self._db = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embedding_model
                )
            else:
                logger.info(f"Creating new vector store at {self.persist_directory}")
                self._db = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embedding_model
                )

            return self._db
        except Exception as e:
            logger.error(
                f"Failed to load or create vector store: {str(e)}",
                exc_info=True,
                extra={"persist_directory": self.persist_directory, "error_type": type(e).__name__}
            )
            raise VectorStoreException(
                user_message="Vector database is temporarily unavailable.",
                details={
                    "persist_directory": self.persist_directory,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="VECTOR_STORE_LOAD_ERROR"
            )

    def add_documents(self, documents: List[Document]):
        """
        Add documents to the vector store incrementally.
        """
        if not documents:
            return

        try:
            db = self.load_or_create()
            db.add_documents(documents)
            logger.info(f"Successfully added {len(documents)} documents to vector store")
        except VectorStoreException:
            # Re-raise vector store exceptions (already logged)
            raise
        except EmbeddingException:
            # Re-raise embedding exceptions (already logged by provider)
            raise
        except Exception as e:
            logger.error(
                f"Failed to add documents to vector store: {str(e)}",
                exc_info=True,
                extra={"num_documents": len(documents), "error_type": type(e).__name__}
            )
            raise VectorStoreException(
                user_message="Failed to store documents in vector database.",
                details={
                    "num_documents": len(documents),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="VECTOR_STORE_ADD_ERROR"
            )

    def add_documents_with_ids(self, documents: List[Document]):
        """
        Add documents with deterministic IDs from metadata.
        
        Expects each document to have metadata['vector_id'].
        This enables idempotent upserts - same ID overwrites existing vector.
        
        Args:
            documents: List of Document objects with vector_id in metadata
        """
        if not documents:
            return

        try:
            db = self.load_or_create()
            
            # Extract IDs from metadata
            ids = [doc.metadata.get("vector_id") for doc in documents]
            
            # Validate all documents have IDs
            if None in ids:
                missing_count = ids.count(None)
                raise ValueError(f"{missing_count} documents missing vector_id in metadata")
            
            # Upsert with explicit IDs (ChromaDB will overwrite if ID exists)
            db.add_documents(documents, ids=ids)
            
            logger.info(f"Successfully upserted {len(documents)} documents with deterministic IDs")
        except VectorStoreException:
            raise
        except EmbeddingException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to add documents with IDs: {str(e)}",
                exc_info=True,
                extra={"num_documents": len(documents), "error_type": type(e).__name__}
            )
            raise VectorStoreException(
                user_message="Failed to store documents in vector database.",
                details={
                    "num_documents": len(documents),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="VECTOR_STORE_ADD_ERROR"
            )

    def delete_by_ids(self, vector_ids: List[str]) -> int:
        """
        Delete vectors by their exact IDs.
        
        This is preferred over metadata-filter deletion because:
        - O(n) performance instead of O(collection_size)
        - Guaranteed precision (no metadata query bugs)
        - Works even if metadata is corrupted
        
        Args:
            vector_ids: List of vector IDs to delete
            
        Returns:
            Count of vectors deleted
        """
        if not vector_ids:
            return 0

        try:
            db = self.load_or_create()
            db.delete(ids=vector_ids)
            logger.info(f"Successfully deleted {len(vector_ids)} vectors by ID")
            return len(vector_ids)
        except Exception as e:
            logger.error(
                f"Failed to delete vectors by IDs: {str(e)}",
                exc_info=True,
                extra={"num_ids": len(vector_ids), "error_type": type(e).__name__}
            )
            raise VectorStoreException(
                user_message="Failed to delete vectors from database.",
                details={
                    "num_ids": len(vector_ids),
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="VECTOR_STORE_DELETE_ERROR"
            )

    def persist(self):
        """
        Chroma auto-persists when persist_directory is set.
        This method exists for API symmetry and future extensibility.
        """
        logger.debug("Vector store auto-persisted (no-op for Chroma)")
        # 👉 We keep the method for:

        # future DBs (FAISS, Pinecone, Qdrant)

        # clean lifecycle symmetry


    def as_retriever(self, **kwargs):
        """
        Return a retriever interface for querying.
        """
        try:
            db = self.load_or_create()
            return db.as_retriever(**kwargs)
        except VectorStoreException:
            # Re-raise vector store exceptions (already logged)
            raise
        except Exception as e:
            logger.error(
                f"Failed to create retriever: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            raise VectorStoreException(
                user_message="Failed to initialize query interface.",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                error_code="VECTOR_STORE_RETRIEVER_ERROR"
            )

