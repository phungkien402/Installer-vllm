"""Query HuggingFace API for model metadata — feed optimizer."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx

HF_API = "https://huggingface.co/api/models"


@dataclass
class ModelMeta:
    hf_id: str                       # "google/medgemma-1.5-4b-it"
    exists: bool
    gated: bool                      # license-gated, cần HF_TOKEN
    accessible: bool                 # token đã accept license chưa
    arch: str                        # "gemma3", "qwen2_vl", ...
    params_b: float                  # 4.0 (billions). 0 = unknown
    is_multimodal: bool              # có image input
    native_context: int              # 128000 / 32768 / ...
    has_chat_template: bool
    recommended_dtype: str           # "bfloat16" / "half"
    raw: dict                        # full response


def _arch_to_dtype(arch: str) -> str:
    """Recommend dtype theo architecture."""
    arch_lc = arch.lower()
    if "gemma" in arch_lc:
        return "bfloat16"  # Gemma 3 tốt nhất BF16
    if "qwen" in arch_lc:
        return "half"      # Qwen-VL hoạt động tốt FP16
    if "llama" in arch_lc:
        return "bfloat16"
    return "bfloat16"


def _parse_params(safetensors: dict) -> float:
    """Lấy số params (B) từ safetensors metadata."""
    total = safetensors.get("total", 0)
    if isinstance(total, dict):
        # newer format: {"F32": int, "BF16": int, ...}
        total = sum(total.values())
    if total == 0:
        return 0.0
    return round(total / 1e9, 2)


def _detect_multimodal(config: dict, arch: str, tags: list[str]) -> bool:
    """Quick detect: model có nhận image không."""
    arch_lc = arch.lower()
    if "vl" in arch_lc or "vision" in arch_lc or "multimodal" in arch_lc:
        return True
    if "vision_config" in config or "image_processor_type" in config:
        return True
    tag_str = " ".join(tags).lower()
    if "image-text-to-text" in tag_str or "multimodal" in tag_str:
        return True
    return False


def _detect_context_length(config: dict) -> int:
    """Lấy max position embeddings (native context)."""
    for k in ("max_position_embeddings", "max_seq_length", "model_max_length"):
        v = config.get(k)
        if isinstance(v, int):
            return v
    # text_config nested (Gemma 3)
    text_cfg = config.get("text_config") or {}
    for k in ("max_position_embeddings", "max_seq_length"):
        v = text_cfg.get(k)
        if isinstance(v, int):
            return v
    return 0


def query(hf_id: str, token: Optional[str] = None, timeout: float = 10.0) -> ModelMeta:
    """Fetch model metadata from HF.

    Args:
        hf_id: e.g. "google/medgemma-1.5-4b-it"
        token: HF token if license-gated.

    Returns:
        ModelMeta with .accessible=False nếu gated + token sai/thiếu.
    """
    token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        r = httpx.get(f"{HF_API}/{hf_id}", headers=headers, timeout=timeout, follow_redirects=True)
    except httpx.RequestError as e:
        return ModelMeta(
            hf_id=hf_id, exists=False, gated=False, accessible=False,
            arch="", params_b=0, is_multimodal=False, native_context=0,
            has_chat_template=False, recommended_dtype="bfloat16",
            raw={"error": str(e)},
        )

    if r.status_code == 404:
        return ModelMeta(
            hf_id=hf_id, exists=False, gated=False, accessible=False,
            arch="", params_b=0, is_multimodal=False, native_context=0,
            has_chat_template=False, recommended_dtype="bfloat16",
            raw={"status": 404},
        )

    if r.status_code in (401, 403):
        # gated repo + no/wrong token
        return ModelMeta(
            hf_id=hf_id, exists=True, gated=True, accessible=False,
            arch="", params_b=0, is_multimodal=False, native_context=0,
            has_chat_template=False, recommended_dtype="bfloat16",
            raw={"status": r.status_code, "body": r.text[:500]},
        )

    if r.status_code != 200:
        return ModelMeta(
            hf_id=hf_id, exists=False, gated=False, accessible=False,
            arch="", params_b=0, is_multimodal=False, native_context=0,
            has_chat_template=False, recommended_dtype="bfloat16",
            raw={"status": r.status_code, "body": r.text[:500]},
        )

    data = r.json()
    gated = data.get("gated", False) is not False
    config = data.get("config") or {}
    safetensors = data.get("safetensors") or {}
    tags = data.get("tags") or []

    arch_list = config.get("architectures") or []
    arch = arch_list[0] if arch_list else config.get("model_type", "")

    return ModelMeta(
        hf_id=hf_id,
        exists=True,
        gated=gated,
        accessible=True,  # 200 OK means token works or repo public
        arch=arch,
        params_b=_parse_params(safetensors),
        is_multimodal=_detect_multimodal(config, arch, tags),
        native_context=_detect_context_length(config),
        has_chat_template="chat_template" in str(data.get("config_sentence_transformers", "")) or True,
        recommended_dtype=_arch_to_dtype(arch),
        raw=data,
    )


def query_awq_variant(base_hf_id: str, token: Optional[str] = None) -> Optional[str]:
    """Tìm AWQ variant của model (community quantize).

    Convention thường: <original>-AWQ hoặc <original>-INT4-AWQ
    """
    candidates = [
        f"{base_hf_id}-AWQ",
        f"{base_hf_id}-INT4-AWQ",
        f"{base_hf_id}-Int4-AWQ",
    ]
    for cand in candidates:
        meta = query(cand, token=token, timeout=5.0)
        if meta.exists and meta.accessible:
            return cand
    return None


if __name__ == "__main__":
    import sys, json
    hf_id = sys.argv[1] if len(sys.argv) > 1 else "google/medgemma-1.5-4b-it"
    meta = query(hf_id)
    out = {k: v for k, v in meta.__dict__.items() if k != "raw"}
    print(json.dumps(out, indent=2, default=str))
