"""Synopsis embeddings (Content DNA).

The architecture names Sentence Transformers (384-dim, matching Title.embedding
Vector(384)). When it is not installed we fall back to TF-IDF + SVD so training
still runs; the embedder name is recorded in the model report.
"""

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer


def _unit(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.where(norms == 0, 1, norms)


class TfidfSvdEmbedder:
    name = "tfidf-svd"

    def __init__(self, dims: int = 32):
        self.dims = dims

    def fit(self, texts: list[str]) -> "TfidfSvdEmbedder":
        self.tfidf_ = TfidfVectorizer(stop_words="english", min_df=2, max_features=3000)
        matrix = self.tfidf_.fit_transform(texts)
        dims = max(1, min(self.dims, matrix.shape[0] - 1, matrix.shape[1] - 1))
        self.svd_ = TruncatedSVD(dims, random_state=0).fit(matrix)
        return self

    def embed(self, texts: list[str]) -> np.ndarray:
        return _unit(self.svd_.transform(self.tfidf_.transform(texts)))


class SentenceTransformerEmbedder:
    name = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def fit(self, texts: list[str]) -> "SentenceTransformerEmbedder":
        return self  # pretrained

    def embed(self, texts: list[str]) -> np.ndarray:
        return _unit(np.asarray(self.model.encode(texts, show_progress_bar=False)))


def get_embedder(prefer: str = "auto"):
    """'auto' tries Sentence Transformers and falls back; 'tfidf' forces the fallback."""
    if prefer != "tfidf":
        try:
            return SentenceTransformerEmbedder()
        except Exception:  # not installed, or the model cannot be downloaded offline
            if prefer == "sentence-transformers":
                raise
    return TfidfSvdEmbedder()
