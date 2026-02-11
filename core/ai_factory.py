import os
from dotenv import load_dotenv

load_dotenv()  

from core.ai_interfaces import LLM, Embeddings
from api.core.logging import get_logger
from api.core.exceptions import LLMException, EmbeddingException

logger = get_logger(__name__)

# OpenAI implementations
from providers.openai.llm import OpenAILLM
from providers.openai.embeddings import OpenAIEmbeddingModel

# Gemini implementations
from providers.gemini.llm import GeminiLLM
from providers.gemini.embeddings import GeminiEmbeddingModel


#local models
from providers.ollama.llm import OllamaLLM
from providers.huggingface.embeddings import HFEmbeddingModel


def get_llm(role: str = "primary") -> LLM:
    """
    Return an LLM instance based on role configuration.

    Example roles:
        - primary
        - summarizer
        - fallback
    """
    role = role.upper()

    provider = os.getenv(f"LLM_{role}_PROVIDER")
    model = os.getenv(f"LLM_{role}_MODEL")

    if not provider or not model:
        logger.error(f"LLM configuration missing for role '{role}'")
        raise ValueError(
            f"LLM configuration missing for role '{role}'"
        )

    provider = provider.lower()

    try:
        if provider == "openai":
            logger.debug(f"Initializing OpenAI LLM: {model}")
            return OpenAILLM(model=model)

        if provider == "gemini":
            logger.debug(f"Initializing Gemini LLM: {model}")
            return GeminiLLM(model=model)

        if provider == "ollama":
            logger.debug(f"Initializing Ollama LLM: {model}")
            return OllamaLLM(model=model)

        logger.error(f"Unsupported LLM provider: {provider}")
        raise ValueError(f"Unsupported LLM provider: {provider}")
    
    except ValueError:
        # Re-raise configuration errors
        raise
    except Exception as e:
        logger.error(
            f"Failed to initialize LLM provider '{provider}': {str(e)}",
            exc_info=True
        )
        raise LLMException(
            user_message=f"Failed to initialize {provider} language model. Please check configuration.",
            details={
                "provider": provider,
                "model": model,
                "role": role,
                "error": str(e),
                "error_type": type(e).__name__
            },
            error_code="LLM_INIT_ERROR"
        )


def get_embeddings(role: str = "default") -> Embeddings:
    """
    Return an Embeddings instance based on role configuration.

    Example roles:
        - default
        - cheap
    """
    role = role.upper()

    provider = os.getenv(f"EMBEDDINGS_{role}_PROVIDER")
    model = os.getenv(f"EMBEDDINGS_{role}_MODEL")

    if not provider or not model:
        logger.error(f"Embeddings configuration missing for role '{role}'")
        raise ValueError(
            f"Embeddings configuration missing for role '{role}'"
        )

    provider = provider.lower()

    try:
        if provider == "openai":
            logger.debug(f"Initializing OpenAI embeddings: {model}")
            return OpenAIEmbeddingModel(model=model)
        
        if provider == "gemini":
            logger.debug(f"Initializing Gemini embeddings: {model}")
            return GeminiEmbeddingModel(model=model)
        
        if provider == "hf":
            logger.debug(f"Initializing HuggingFace embeddings: {model}")
            return HFEmbeddingModel(model=model)

        logger.error(f"Unsupported Embeddings provider: {provider}")
        raise ValueError(f"Unsupported Embeddings provider: {provider}")
    
    except ValueError:
        # Re-raise configuration errors
        raise
    except Exception as e:
        logger.error(
            f"Failed to initialize Embeddings provider '{provider}': {str(e)}",
            exc_info=True
        )
        raise EmbeddingException(
            user_message=f"Failed to initialize {provider} embeddings. Please check configuration.",
            details={
                "provider": provider,
                "model": model,
                "role": role,
                "error": str(e),
                "error_type": type(e).__name__
            },
            error_code="EMBEDDING_INIT_ERROR"
        )






# Responsibility of ai_factory.py

# Read environment variables

# Decide which provider to use

# Return an object that matches the interface

# Conceptually:
# get_llm("primary")      -> returns LLM interface
# get_embeddings("default") -> returns Embeddings interface

# 🚨 Key rule
# Your pipeline will talk ONLY to this factory.

# Never again:

# ChatOpenAI(...)
# OpenAIEmbeddings(...)




# Deep code analysis

# Let’s break this down slowly (this is important)
# 1️⃣ Why roles are uppercased
# role = role.upper()


# So this works safely:

# get_llm("primary")
# get_llm("Primary")
# get_llm("PRIMARY")


# And maps to:

# LLM_PRIMARY_PROVIDER

# 2️⃣ Why environment variables, not arguments?

# Because:

# deployment config ≠ code

# dev/test/prod differences belong in environment

# Kubernetes, Docker, CI/CD all rely on env vars

# This is 12-factor app design (industry standard).

# 3️⃣ Why if provider == "openai"?

# Because this is where provider expansion happens later:

# if provider == "openai":
#     ...
# elif provider == "ollama":
#     ...
# elif provider == "hf":
#     ...


# This file is the single switchboard.

# 4️⃣ Why return interface types?
# def get_llm(...) -> LLM:


# This guarantees:

# callers only rely on the interface

# no provider-specific behavior leaks

# Even though we return OpenAILLM,
# the caller treats it as LLM.

# What happens end-to-end (mentally simulate)
# llm = get_llm("primary")


# Reads LLM_PRIMARY_PROVIDER

# Reads LLM_PRIMARY_MODEL

# Chooses OpenAILLM

# Returns object with .invoke()

# Pipeline doesn’t care how.

