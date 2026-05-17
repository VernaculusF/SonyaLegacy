"""Local embedding model for episodic memory recall.

Uses `fastembed` (ONNX Runtime backend) with `all-MiniLM-L6-v2`. Chosen over
`sentence-transformers` because it ships without torch — ~150 MB on disk vs
~1 GB, ~120 MB RAM at runtime, faster inference on CPU with AVX2.

Lazy-loaded: model is only initialised on first call to `encode()` so import
of this module is free and unit tests don't pay the cost.

Embedding format: float32 numpy array, dim=384, L2-normalized so similarity
is a plain dot product. Stored in substrate as raw bytes (1536 bytes/row).

Both `numpy` and `fastembed` are imported lazily so this module is safe to
import in environments without them (e.g. dev machines, CI). Callers should
always check `Embedder.is_available()` before relying on `encode()`.
"""

from __future__ import annotations

import importlib.util
import threading
from typing import Iterable

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_DIM = 384


class EmbedderUnavailableError(RuntimeError):
    """Raised when encode() is called but fastembed/numpy aren't installed."""


class Embedder:
    """Singleton-ish wrapper around fastembed.TextEmbedding.

    Thread-safe lazy init. Use `Embedder.shared()` for the process-wide
    instance, or construct a fresh one (mostly for tests).
    """

    _shared_instance: "Embedder | None" = None
    _shared_lock = threading.Lock()

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None  # lazy
        self._lock = threading.Lock()

    @classmethod
    def shared(cls) -> "Embedder":
        with cls._shared_lock:
            if cls._shared_instance is None:
                cls._shared_instance = cls()
            return cls._shared_instance

    @staticmethod
    def is_available() -> bool:
        """True if both fastembed and numpy are importable. Cheap probe."""
        try:
            return (
                importlib.util.find_spec("fastembed") is not None
                and importlib.util.find_spec("numpy") is not None
            )
        except Exception:
            return False

    @property
    def dim(self) -> int:
        return _DIM

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                from fastembed import TextEmbedding  # type: ignore[import-not-found]
            except ImportError as exc:
                raise EmbedderUnavailableError(
                    "fastembed not installed; pip install fastembed"
                ) from exc
            # fastembed downloads model files into ~/.cache/fastembed/ on first use.
            self._model = TextEmbedding(model_name=self._model_name)

    def encode(self, texts: Iterable[str]):
        """Encode a batch of texts. Returns (N, 384) float32 L2-normalized.

        Empty / None inputs are coerced to empty string. Caller is expected to
        have filtered obvious garbage already.
        """
        try:
            import numpy as np
        except ImportError as exc:
            raise EmbedderUnavailableError(
                "numpy not installed; pip install numpy"
            ) from exc
        self._ensure_loaded()
        prepared = [(t or "").strip() or " " for t in texts]
        # fastembed returns a generator of np.ndarray rows.
        vectors = list(self._model.embed(prepared))  # type: ignore[union-attr]
        if not vectors:
            return np.zeros((0, _DIM), dtype=np.float32)
        arr = np.asarray(vectors, dtype=np.float32)
        # fastembed's output is already L2-normalized for this model, but we
        # re-normalize defensively so cosine == dot product unconditionally.
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def encode_one(self, text: str):
        """Encode a single text, returning (384,) float32."""
        out = self.encode([text])
        return out[0]


def vector_to_blob(vec) -> bytes:
    """Serialize a (384,) float32 vector for sqlite BLOB storage."""
    import numpy as np  # local — keep module import-safe without numpy
    if vec.dtype != np.float32:
        vec = vec.astype(np.float32)
    return vec.tobytes()


def blob_to_vector(blob: bytes):
    """Inverse of vector_to_blob."""
    import numpy as np
    return np.frombuffer(blob, dtype=np.float32)
