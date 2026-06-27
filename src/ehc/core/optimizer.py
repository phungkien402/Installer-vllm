"""Dynamic optimizer — tính args vLLM dựa trên HW + model meta.

Không dùng preset hardcode. Mọi quyết định derived từ:
  - GPU spec (VRAM, compute capability, FP8/AWQ support)
  - Model meta từ HF (params, arch, multimodal)
  - VRAM budget còn lại (multi-model)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ehc.core.detect import GPUInfo
from ehc.core.hf_meta import ModelMeta


# Heuristic constants
SAFETY_BUFFER_MB = 800            # luôn chừa cho CUDA context + activations spike
KV_BYTES_PER_TOKEN_DEFAULT = 100_000   # ~100KB/token (3-4B model average)
DEFAULT_TARGET_CONTEXT = 8192    # max-len target nếu model hỗ trợ
MIN_MAX_LEN = 2048
EAGER_MEMORY_SAVING_MB = 700      # giả định eager save bao nhiêu so với CUDA graph


@dataclass
class VLLMArgs:
    """Args sẵn sàng pass vào `docker run vllm/vllm-openai`."""
    model: str                              # HF id thật để load
    served_model_name: Optional[str] = None # tên expose (giữ tương thích với OCR code)
    quantization: Optional[str] = None      # "awq_marlin" / "fp8" / None
    dtype: str = "bfloat16"
    gpu_memory_utilization: float = 0.50
    max_model_len: int = 4096
    enforce_eager: bool = False
    limit_mm_per_prompt: Optional[str] = None  # '{"image": 1}' or None
    extra: dict = field(default_factory=dict)

    # Diagnostic — không pass cho vLLM, dùng để show plan
    estimated_vram_mb: int = 0
    rationale: list[str] = field(default_factory=list)


def _model_size_mb(params_b: float, dtype: str, quant: Optional[str]) -> int:
    """Ước tính model weights size theo dtype/quant."""
    bytes_per_param = {
        "float32": 4, "fp32": 4,
        "float16": 2, "fp16": 2, "half": 2,
        "bfloat16": 2, "bf16": 2,
    }.get(dtype.lower(), 2)

    if quant == "fp8":
        bytes_per_param = 1
    elif quant in ("awq_marlin", "awq", "gptq"):
        bytes_per_param = 0.5  # int4

    return int(params_b * 1000 * bytes_per_param)


def _kv_cache_mb(max_len: int, kv_per_token: int = KV_BYTES_PER_TOKEN_DEFAULT) -> int:
    """KV cache cho 1 sequence (concurrent=1)."""
    return int((max_len * kv_per_token) / (1024 * 1024))


def _pick_quantization(
    model_meta: ModelMeta,
    gpu: GPUInfo,
    available_mb: int,
    base_size_mb_bf16: int,
) -> tuple[Optional[str], str]:
    """Chọn quantization phù hợp với HW + budget.

    Return: (quant_name | None, reason)
    """
    # Nếu VRAM dư dả → không quantize
    if base_size_mb_bf16 < available_mb * 0.4:
        return None, "VRAM dư, giữ BF16/FP16 cho chất lượng tốt nhất"

    # Cần quantize
    has_awq = bool(getattr(model_meta, "awq_id", None))

    # FP8 ưu tiên với GPU mới (Ada/Hopper/Blackwell)
    if gpu.supports_fp8:
        return "fp8", f"FP8 (GPU sm_{gpu.compute_capability[0]}{gpu.compute_capability[1]} hỗ trợ native)"

    # AWQ marlin nếu có variant + Ampere+
    if has_awq and gpu.supports_awq_marlin:
        return "awq_marlin", "AWQ int4 (community variant + Marlin kernels)"

    # Không có lựa chọn — giữ BF16, có thể OOM
    return None, "Không có quantize phù hợp, giữ BF16 (có thể OOM nếu VRAM tight)"


def _pick_max_len(model_meta: ModelMeta, available_for_kv_mb: int) -> int:
    """Chọn max-model-len: min(native_context, target, fit_budget)."""
    target = min(DEFAULT_TARGET_CONTEXT, model_meta.native_context or DEFAULT_TARGET_CONTEXT)

    # KV budget có thể chứa bao nhiêu token
    max_tokens_fit = int(available_for_kv_mb * 1024 * 1024 / KV_BYTES_PER_TOKEN_DEFAULT)
    capped = min(target, max_tokens_fit)

    # Round down to nearest power-of-2-ish
    if capped >= 16384: return 16384
    if capped >= 10240: return 10240
    if capped >= 8192:  return 8192
    if capped >= 6144:  return 6144
    if capped >= 4096:  return 4096
    if capped >= 2048:  return 2048
    return MIN_MAX_LEN


def optimize_one(
    model_meta: ModelMeta,
    gpu: GPUInfo,
    vram_budget_mb: int,
    other_models_using_mb: int = 0,
) -> VLLMArgs:
    """Tính args tối ưu cho 1 model.

    Args:
        vram_budget_mb: VRAM còn lại để allocate cho model này
        other_models_using_mb: tổng VRAM model khác đang/sẽ dùng (để tính util đúng)
    """
    rationale: list[str] = []

    total_vram = gpu.vram_mb
    safety = SAFETY_BUFFER_MB
    available = max(0, vram_budget_mb - safety)
    rationale.append(f"Budget: {vram_budget_mb} MB - safety {safety} = {available} MB usable")

    if model_meta.params_b == 0:
        rationale.append("⚠ Model size unknown (safetensors metadata missing), fallback to 4B estimate")
        params_b = 4.0
    else:
        params_b = model_meta.params_b

    # 1. Ước tính size BF16 baseline
    bf16_size = _model_size_mb(params_b, "bfloat16", None)
    rationale.append(f"Model BF16 weights: ~{bf16_size} MB ({params_b}B params × 2 bytes)")

    # 2. Chọn quantization
    quant, q_reason = _pick_quantization(model_meta, gpu, available, bf16_size)
    rationale.append(f"Quantization: {quant or 'none'} — {q_reason}")
    dtype = model_meta.recommended_dtype
    weights_mb = _model_size_mb(params_b, dtype, quant)

    # 3. KV cache budget = available - weights - activations
    activations_mb = 500
    kv_budget = max(0, available - weights_mb - activations_mb)
    rationale.append(f"Weights {weights_mb} + activations {activations_mb} MB → KV budget {kv_budget} MB")

    # 4. Pick max-model-len
    max_len = _pick_max_len(model_meta, kv_budget)
    kv_for_target = _kv_cache_mb(max_len)
    rationale.append(f"max_model_len = {max_len} (KV ~{kv_for_target} MB)")

    # 5. enforce_eager: bật khi VRAM tight
    total_using = weights_mb + activations_mb + kv_for_target
    headroom = available - total_using
    if headroom < EAGER_MEMORY_SAVING_MB or (other_models_using_mb > 0):
        enforce_eager = True
        rationale.append(f"enforce_eager=true (headroom {headroom} MB < {EAGER_MEMORY_SAVING_MB} hoặc share GPU)")
    else:
        enforce_eager = False
        rationale.append(f"enforce_eager=false (headroom {headroom} MB đủ cho CUDA graph cache)")

    # 6. GPU memory utilization (tỉ lệ TỔNG VRAM model này được phép dùng)
    util = round(total_using / total_vram, 2)
    util = max(0.20, min(util, 0.95))
    rationale.append(f"gpu_memory_utilization = {util} (= {total_using} / {total_vram} MB total)")

    # 7. Multimodal flag
    limit_mm = '{"image": 1}' if model_meta.is_multimodal else None
    if limit_mm:
        rationale.append("limit_mm_per_prompt enabled (model is multimodal)")

    # 8. Choose actual HF id to load (AWQ variant if quantization picked AWQ)
    actual_model = model_meta.hf_id
    served_name = None
    if quant == "awq_marlin":
        awq_id = getattr(model_meta, "awq_id", None)
        if awq_id:
            actual_model = awq_id
            served_name = model_meta.hf_id  # serve dưới tên gốc cho compat
            rationale.append(f"Load {awq_id} but expose as {model_meta.hf_id}")

    return VLLMArgs(
        model=actual_model,
        served_model_name=served_name,
        quantization=quant,
        dtype=dtype,
        gpu_memory_utilization=util,
        max_model_len=max_len,
        enforce_eager=enforce_eager,
        limit_mm_per_prompt=limit_mm,
        estimated_vram_mb=total_using,
        rationale=rationale,
    )


def optimize_many(
    models: list[ModelMeta],
    gpu: GPUInfo,
) -> list[VLLMArgs]:
    """Optimize multi-model. Phân bổ VRAM theo thứ tự (model lớn trước)."""
    # Sort by params desc — model lớn được tính budget trước
    sorted_idx = sorted(range(len(models)), key=lambda i: models[i].params_b, reverse=True)

    total_budget = gpu.vram_mb
    plans: list[Optional[VLLMArgs]] = [None] * len(models)

    # Round 1: estimate share equally
    n = len(models)
    if n == 0:
        return []
    share = total_budget // n

    # Calculate each model's needs with equal initial share
    others_using = 0
    for idx in sorted_idx:
        plan = optimize_one(
            models[idx], gpu,
            vram_budget_mb=share,
            other_models_using_mb=others_using,
        )
        plans[idx] = plan
        others_using += plan.estimated_vram_mb

    # Round 2: redistribute leftover to larger models (if total < total_budget)
    used = sum(p.estimated_vram_mb for p in plans if p)
    leftover = total_budget - used - SAFETY_BUFFER_MB
    if leftover > 1000:  # > 1GB unused → upgrade biggest model
        biggest_idx = sorted_idx[0]
        new_budget = (total_budget // n) + leftover
        plans[biggest_idx] = optimize_one(
            models[biggest_idx], gpu,
            vram_budget_mb=new_budget,
            other_models_using_mb=used - plans[biggest_idx].estimated_vram_mb,
        )
        plans[biggest_idx].rationale.append(f"+ {leftover} MB leftover redistributed")

    return [p for p in plans if p is not None]
