"""
Embeddings Module
==================
Wrapper around sentence-transformers for computing text embeddings.
Uses all-MiniLM-L6-v2 model (384-dimensional embeddings).
"""

import numpy as np
from sentence_transformers import SentenceTransformer


# Module-level singleton for the model
_model = None


def get_model() -> SentenceTransformer:
    """Get or create the module-level SentenceTransformer singleton."""
    global _model
    if _model is None:
        print("Loading sentence-transformers model: all-MiniLM-L6-v2...")
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("[OK] Model loaded")
    return _model


def get_embedding(text: str) -> np.ndarray:
    """
    Compute embedding for a single text string.

    Args:
        text: Input text to embed.

    Returns:
        384-dimensional numpy array.
    """
    model = get_model()
    return model.encode(text, convert_to_numpy=True, show_progress_bar=False)


def get_embeddings_batch(texts: list) -> np.ndarray:
    """
    Compute embeddings for a batch of text strings.

    Args:
        texts: List of input texts to embed.

    Returns:
        numpy array of shape (len(texts), 384).
    """
    model = get_model()
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=True,
                        batch_size=32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    Returns:
        Float in [-1, 1], but typically [0, 1] for text embeddings.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


if __name__ == "__main__":
    # Quick test
    texts = [
        "Senior Python developer with Django and PostgreSQL experience",
        "Experienced data analyst proficient in SQL, Tableau, and Python",
        "Marketing manager specializing in SEO and content strategy",
    ]

    embeddings = get_embeddings_batch(texts)
    print(f"Embedding shape: {embeddings.shape}")

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            print(f"Similarity({i}, {j}): {sim:.4f}")
