"""Local-directory ONNX embedding backend (e.g. a BAAI/bge-m3 snapshot on disk).

Loads ``tokenizer.json`` + ``model.onnx`` straight from a user-provided model
directory — zero downloads, zero network. CLS pooling + L2 normalisation
matches the sentence-transformers ``1_Pooling`` config shipped with bge-m3
(``word_embedding_dimension: 1024``).

Enabled via settings key ``knowledge_local_embedding_dir`` (or env
``OCTOP_KNOWLEDGE_LOCAL_EMBEDDING_DIR``) together with
``knowledge_embedding_backend = "local"``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Sequence

logger = logging.getLogger(__name__)

SETTINGS_KEY = "knowledge_local_embedding_dir"
ENV_KEY = "OCTOP_KNOWLEDGE_LOCAL_EMBEDDING_DIR"

# bge-m3: max_position_embeddings=8194, keep a small safety margin.
_MAX_TOKENS = 8192

_REQUIRED_FILES = ("tokenizer.json",)
_ONNX_CANDIDATES = ("onnx/model.onnx", "onnx/model_optimized.onnx", "model.onnx")

# Process-wide cache: loading a 2.27 GB ONNX session is expensive, reuse it.
_cache: dict[str, Any] = {}
_cache_key: str | None = None


def resolve_local_dir(settings_get: Callable[[str], str | None]) -> str:
    """Return the configured local model directory (settings first, env fallback)."""
    raw = ""
    try:
        raw = (settings_get(SETTINGS_KEY) or "").strip()
    except Exception:  # pragma: no cover - settings backend failure falls back to env
        raw = ""
    if not raw:
        raw = os.environ.get(ENV_KEY, "").strip()
    return raw


def find_onnx_weights(directory: Path) -> Path | None:
    """Locate the first usable ONNX weight file inside *directory*."""
    for rel in _ONNX_CANDIDATES:
        candidate = directory / rel
        if candidate.is_file():
            return candidate
    return None


def local_dir_ready(directory: str) -> bool:
    """True when *directory* holds both tokenizer.json and ONNX weights."""
    if not directory:
        return False
    path = Path(directory)
    if not path.is_dir():
        return False
    if not all((path / name).is_file() for name in _REQUIRED_FILES):
        return False
    return find_onnx_weights(path) is not None


def require_local_dir(directory: str) -> Path:
    """Validate and return the model directory, raising a readable error."""
    if not local_dir_ready(directory):
        raise RuntimeError(
            f"local embedding directory is not usable: {directory or '(unset)'}; "
            "it must contain tokenizer.json and model.onnx"
        )
    return Path(directory)


def _load(directory: Path) -> tuple[Any, Any]:
    """Load (and cache) the fast tokenizer and ONNX inference session."""
    global _cache_key
    key = str(directory)
    if _cache_key == key and _cache.get("tok") is not None and _cache.get("sess") is not None:
        return _cache["tok"], _cache["sess"]

    import onnxruntime
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=_MAX_TOKENS)

    onnx_path = find_onnx_weights(directory)
    if onnx_path is None:  # defensive: require_local_dir already checked
        raise RuntimeError(f"no ONNX weights found under {directory}")
    logger.info("loading local embedding model from %s (this may take a while)", onnx_path)
    session = onnxruntime.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )

    _cache["tok"] = tokenizer
    _cache["sess"] = session
    _cache_key = key
    return tokenizer, session


def _cls_pool_and_normalize(hidden: Any) -> list[float]:
    """CLS pooling (first token) + L2 normalisation, matching bge-m3 usage."""
    import numpy as np

    vector = hidden[0, 0] if getattr(hidden, "ndim", 0) == 3 else hidden[0]
    vector = np.asarray(vector, dtype="float32")
    norm = float(np.sqrt((vector * vector).sum()))
    if norm <= 0.0:
        norm = 1.0
    return [float(x) for x in (vector / norm)]


def embed_texts_local(directory: str, texts: Sequence[str]) -> list[list[float]]:
    """Embed *texts* with a local ONNX model directory; output order preserved."""
    if not texts:
        return []
    path = require_local_dir(directory)
    tokenizer, session = _load(path)

    input_names = [item.name for item in session.get_inputs()]
    output_names = [item.name for item in session.get_outputs()]
    out_name = output_names[0] if output_names else "last_hidden_state"

    out: list[list[float]] = []
    for text in texts:
        encoding = tokenizer.encode(text if text else " ")
        ids = [int(x) for x in encoding.ids]
        mask = [int(x) for x in encoding.attention_mask]
        feed: dict[str, Any] = {}
        for name in input_names:
            if name == "input_ids":
                feed[name] = [ids]
            elif name == "attention_mask":
                feed[name] = [mask]
            elif name == "token_type_ids":
                feed[name] = [[0] * len(ids)]
        if "input_ids" not in feed:
            raise RuntimeError(
                f"unexpected ONNX model inputs: {input_names}; expected input_ids"
            )
        results = session.run([out_name], feed)
        out.append(_cls_pool_and_normalize(results[0]))
    if len(out) != len(texts):
        raise RuntimeError("embedding count mismatch")
    return out
