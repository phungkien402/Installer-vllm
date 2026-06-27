# ehc-installer

> **Textual TUI** + headless CLI để cài đặt EHC HealthCare AI stack (OCR + CDSS).
> Target: DevOps team EHC, Ubuntu 22.04 / 24.04, NVIDIA GPU.

---

## Quick start trên server BV

```bash
# 1-line install
curl -fsSL https://raw.githubusercontent.com/phungkien402/installer-vllm/main/install.sh | bash

# Hoặc clone manual
git clone https://github.com/phungkien402/installer-vllm.git
cd ehc-installer
bash install.sh

# Launch TUI
ehc
```

`install.sh` tự:
- Cài Python 3 + git + curl (apt)
- Clone repo
- Tạo venv `.venv`
- `pip install -e .`
- Đặt wrapper `/usr/local/bin/ehc` (cần sudo)

→ Sau đó gõ `ehc` chạy được mọi nơi.

---

## TUI flow

```
ehc

→ Welcome
   ▶ Start setup        ← Enter
     Check environment
     vLLM management
     Quit

→ Detect
   OS, GPU, deps panel
   ▶ Next: install deps

→ Install Deps
   ☑ docker
   ☑ nvidia-container-toolkit
   ☑ tailscale
   ▶ Install selected

→ Models
   [Input HF id...] [Add]
   ┌─ Queue ─────────────────────────────────┐
   │ Qwen/Qwen2.5-VL-3B  AWQ  6.4GB  4096   │
   │ google/medgemma-1.5-4b-it  FP8  9.0GB │
   └─────────────────────────────────────────┘
   ▶ Install all

→ Stack Setup
   BV name: [ocr-bv-noibai]
   ▶ Run setup       ← clone OCR repo, generate compose, start, Tailscale

→ Done
   URLs + tokens
```

---

## Headless CLI (cho automation / CI)

```bash
# Dependencies
ehc deps check
ehc deps install

# vLLM models
ehc vllm optimize Qwen/Qwen2.5-VL-3B-Instruct   # show plan only
ehc vllm install Qwen/Qwen2.5-VL-3B-Instruct
ehc vllm install google/medgemma-1.5-4b-it --apply
ehc vllm list
ehc vllm logs vllm-medgemma-1-5-4b-it -f
ehc vllm remove vllm-qwen2-5-vl-3b-instruct-awq

# Stack
ehc stack setup --bv-name=ocr-bv-noibai
ehc stack info
ehc stack test
ehc stack logs ocr-server -f
ehc stack restart
ehc stack destroy

# Aggregate
ehc status
```

---

## Module tách riêng

| Module | Trách nhiệm | Khi fail |
|---|---|---|
| `deps`  | System packages | `ehc deps install <name>` retry |
| `vllm`  | vLLM container per model | `ehc vllm install <id>` retry |
| `stack` | OCR + proxy + Tailscale | `ehc stack setup` rerun (idempotent) |

→ Không monolithic. Mỗi module fail debug độc lập.

---

## Dynamic optimizer

Khi `ehc vllm install <hf-id>`:

1. Query **HuggingFace API** → metadata (params, arch, gated, multimodal, native context).
2. Detect **GPU** (VRAM, compute capability, FP8/AWQ support).
3. Tính args:
   - Quantization (FP8 / AWQ / none) auto chọn.
   - `gpu_memory_utilization`, `max_model_len`, `enforce_eager`.
4. Show plan + rationale.
5. Confirm → `docker run`.

→ Adapt mọi GPU mới (RTX 6000, A100, H100, ...) **không cần update preset**.

---

## Auto-clone OCR repo

Stack setup tự clone `github.com/phungkien402/ocr` (configurable). User chỉ clone `ehc-installer`, không cần clone OCR repo riêng.

---

## State / outputs

```
~/OCR_PHR/                              # OCR repo clone
├── docker-compose.yml
├── OCR_server/.env                     # auto-generated, chmod 600
├── .env                                # ngrok dummy + tg placeholders
├── .vllm_proxy.env                     # VLLM_PROXY_KEY, chmod 600
└── tools/vllm_auth_proxy.py

~/.cache/huggingface/                   # vLLM model cache
```

---

## Dev mode

```bash
git clone https://github.com/phungkien402/installer-vllm.git
cd ehc-installer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/

# Build binary
make build
./dist/ehc --help
```

---

## Roadmap

- [x] Phase 1: Skeleton + TUI + dynamic optimizer + Ubuntu installer
- [x] Phase 2 part 1: Stack setup execution (clone + generate + start + Tailscale)
- [ ] Phase 2 part 2: State persist + resume sau reboot
- [ ] Phase 3: Live VRAM track, warmup integration, PyInstaller binary
- [ ] Phase 4: Cross-platform (Windows WSL2)

Chi tiết: xem `PROGRESS.md`.

---

## Push lên GitHub (lần đầu)

```bash
# Tạo repo `ehc-installer` trên GitHub (private hoặc public).
# Sau đó local:
cd ehc-installer
git init
git add .
git commit -m "Initial commit: ehc-installer phase 1"
git branch -M main
git remote add origin https://github.com/phungkien402/installer-vllm.git
git push -u origin main
```

Sau đó server BV chỉ cần:
```bash
curl -fsSL https://raw.githubusercontent.com/phungkien402/installer-vllm/main/install.sh | bash
ehc
```
