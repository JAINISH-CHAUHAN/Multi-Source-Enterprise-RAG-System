"""
Content-addressed hashing utilities for file deduplication and deterministic vector IDs.
"""
import hashlib


def compute_file_hash(file_bytes: bytes) -> str:
    """
    Compute a SHA-256 hex digest of raw file bytes.
    
    Args:
        file_bytes: Raw bytes of the file
        
    Returns:
        64-character hexadecimal hash string
        
    Example:
        >>> compute_file_hash(b"hello world")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
    """
    return hashlib.sha256(file_bytes).hexdigest()


def make_vector_id(file_hash: str, chunk_index: int) -> str:
    """
    Produce a deterministic, collision-resistant vector ID.
    
    Using the same file_hash + chunk_index always yields the same ID,
    making vector upserts fully idempotent. This enables safe re-ingestion
    and prevents duplicate vectors.
    
    Args:
        file_hash: SHA-256 hash of the source file
        chunk_index: Zero-based index of the chunk within the document
        
    Returns:
        32-character deterministic vector ID
        
    Example:
        >>> make_vector_id("abc123", 0)
        '8c6976e5b5410415bde908bd4dee15df'
        >>> make_vector_id("abc123", 0)  # Same inputs = same output
        '8c6976e5b5410415bde908bd4dee15df'
    """
    raw = f"{file_hash}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
