from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # Strong default for speed/quality
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    if isinstance(vectors, np.ndarray):
        return vectors.tolist()
    return [v.tolist() for v in vectors]