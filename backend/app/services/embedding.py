import logging
from pathlib import Path

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _has_directml() -> bool:
    """Check if ONNX Runtime with DirectML is available."""
    try:
        import onnxruntime as ort
        return "DmlExecutionProvider" in ort.get_available_providers()
    except ImportError:
        return False


def _load_model():
    """Load the embedding model (GPU via ONNX+DirectML, or CPU via PyTorch)."""
    global _model
    if _model is not None:
        return _model

    if _has_directml():
        _model = _load_onnx_directml_model()
    else:
        _model = _load_pytorch_model()

    return _model


def _load_pytorch_model():
    """Load the model with standard PyTorch (CPU fallback)."""
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model: %s on CPU...", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)
    logger.info("Embedding model loaded (CPU).")
    return ("pytorch", model)


def _find_onnx_model_path() -> Path:
    """Find the ONNX model in HuggingFace cache, exporting if needed."""
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_name = settings.embedding_model.replace("/", "--")
    model_dir = cache_dir / f"models--{model_name}"

    # Check if ONNX model already exists in cache
    onnx_path = None
    if model_dir.exists():
        for p in model_dir.rglob("model.onnx"):
            onnx_path = p
            break

    if onnx_path and onnx_path.exists():
        return onnx_path

    # Export via sentence-transformers (triggers ONNX export + caching)
    logger.info("ONNX model not found in cache, exporting...")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(settings.embedding_model, backend="onnx")

    # Find it now
    for p in model_dir.rglob("model.onnx"):
        return p

    raise FileNotFoundError(f"Could not find ONNX model after export in {model_dir}")


def _load_onnx_directml_model():
    """Load the model as ONNX and run inference via DirectML on AMD GPU.

    Uses basic graph optimization to avoid fused operators that may not be
    supported on all DirectML devices (e.g. RDNA 4 GPUs).
    """
    import onnxruntime as ort
    from transformers import AutoTokenizer

    logger.info(
        "Loading embedding model: %s with ONNX+DirectML (GPU)...",
        settings.embedding_model,
    )

    onnx_path = _find_onnx_model_path()
    logger.info("ONNX model path: %s", onnx_path)

    # Create session with basic optimization (no fused ops that break on RDNA 4)
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC

    session = ort.InferenceSession(
        str(onnx_path),
        sess_options=sess_options,
        providers=["DmlExecutionProvider", "CPUExecutionProvider"],
    )

    tokenizer = AutoTokenizer.from_pretrained(settings.embedding_model)

    logger.info("Embedding model loaded (ONNX+DirectML GPU).")
    return ("onnx", session, tokenizer)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using bge-m3.

    Returns a list of float vectors (1024-dim for bge-m3).
    """
    model_info = _load_model()

    if model_info[0] == "onnx":
        return _embed_onnx(texts, model_info[1], model_info[2])
    else:
        model = model_info[1]
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()


def _embed_onnx(texts: list[str], session, tokenizer) -> list[list[float]]:
    """Run embedding inference directly through the ONNX session."""
    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="np",
    )

    outputs = session.run(
        ["sentence_embedding"],
        {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64),
        },
    )

    embeddings = outputs[0]

    # L2-normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    embeddings = embeddings / norms

    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Generate a single embedding for a query string."""
    return embed_texts([text])[0]
