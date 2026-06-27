# ehc-installer — Progress

> Tiến độ phát triển công cụ TUI cài đặt EHC HealthCare AI stack.

---

## Phase 1 — Skeleton ✅

**Status:** Hoàn thành 2026-06-26

### Done

- [x] Project structure (pyproject.toml, Makefile, src layout)
- [x] CLI entry với typer + dispatch sang Textual TUI
- [x] **`detect.py`** — phát hiện OS, GPU (NVIDIA), driver, CUDA, compute capability, FP8/AWQ support
- [x] **`hf_meta.py`** — query HuggingFace API → params, arch, multimodal, native context, gated check
- [x] **`optimizer.py`** — dynamic VRAM optimizer:
  - Tự chọn quantization (FP8 / AWQ / none) theo HW + budget
  - Tính `gpu_memory_utilization`, `max_model_len`, `enforce_eager`
  - Multi-model VRAM phân bổ (round 1 share equal, round 2 redistribute leftover)
  - Rationale log cho từng quyết định
- [x] **`commands/deps.py`** — `ehc deps check` + `ehc deps install` headless
- [x] **`commands/vllm.py`** — `optimize`, `install`, `list`, `remove`, `logs`, `doctor`
- [x] **`core/install/ubuntu.py`** — installer Docker CE, NVIDIA Container Toolkit, Tailscale (Ubuntu 22.04/24.04)
- [x] **Textual TUI screens:**
  - `welcome.py` — splash + menu
  - `detect.py` — OS + GPU + deps panel
  - `install_deps.py` — checkboxes + live install log
  - `models.py` — input HF id, queue, optimizer plan table, install
  - `stack_setup.py` — form (stub)
  - `done.py` — summary
  - `help.py`
- [x] `styles.tcss` — Textual CSS theme

### Decisions locked in

| Decision | Value |
|---|---|
| Target platform | Linux (Ubuntu 22.04 + 24.04) phase 1 |
| Model registry | **Dynamic** (user nhập HF id, không hardcode) |
| Module pattern | Tách `deps` / `vllm` / `stack` — debug retry độc lập |
| VRAM allocation | Dynamic optimizer, không preset YAML theo HW |
| UI mode | **Textual full-screen TUI** + headless CLI |
| Auto-install dep | Có (Docker, NVIDIA Container Toolkit, Tailscale) |
| Token storage | `~/.ehc/tokens.env` (chmod 600) |
| Distribution | PyInstaller binary single-file + pip editable |

---

## Phase 2 — Stack Setup + State (in progress)

**Mục tiêu:** Hoàn thiện end-to-end deploy 1 BV.

### Done

- [x] **`core/stack.py`** — full pipeline:
  - Clone/update OCR repo (`clone_or_update`)
  - Generate `OCR_server/.env` + top-level `.env` + `.vllm_proxy.env`
  - Auto-generate API keys (OCR_API_KEY, VLLM_PROXY_KEY)
  - `docker compose build + up -d` ocr-server + monitor
  - Start auth proxy background
  - Tailscale up + Funnel enable (port 443 + 8443)
  - `print_handover()` show URL + tokens
- [x] **`commands/stack.py` thực thi:**
  - `setup` (full pipeline)
  - `info` (read existing .env, print handover)
  - `test` (smoke test /health + /v1/extract)
  - `restart`, `logs`, `destroy`
- [x] **`tui/screens/stack_setup.py` wire** vào `core/stack.py`
- [x] **`install.sh` bootstrap** — clone repo + venv + pip install + wrapper /usr/local/bin/ehc

### Pending Phase 2

- [ ] **State persist `~/.ehc/state.json`**:
  - bv_name, models_installed, last_phase, timestamps
  - Resume sau reboot (driver mới cài cần reboot)
- [ ] **`ehc resume`** — đọc state, tiếp tục từ phase last
- [ ] **Templates Jinja2:**
  - `docker-compose.yml.j2` (hiện đang dùng compose có sẵn trong OCR repo)
  - `vllm_auth_proxy.py` (copy/embed thay vì depend vào OCR repo)

### Tests cần viết

- [ ] `test_optimizer.py` — unit test cho các scenario:
  - RTX 5080 16GB + Qwen 3B + MedGemma 4B → quantize đúng
  - RTX 4090 24GB + 2 model → bỏ enforce-eager
  - A100 80GB + 4 model → tất cả BF16
  - GPU 8GB + 4B model → AWQ
- [ ] `test_hf_meta.py` — mock httpx
- [ ] `test_detect.py` — mock subprocess

---

## Phase 3 — Polish (TODO)

- [ ] **Live VRAM track** trong models screen (progress bar realtime)
- [ ] **Warmup integration** — chạy `warmup_vllm.sh` sau install
- [ ] **PyInstaller binary** single-file `ehc` ~50MB
- [ ] **GitHub Actions** CI: lint + test + build binary release
- [ ] **Update command** `ehc update` — pull repo + rebuild
- [ ] **Backup/restore** — export config + data
- [ ] **NVIDIA driver auto-detect missing** — installer cài + nhắc reboot
- [ ] **Resume mechanism sau reboot**

---

## Phase 4 — Cross-platform (TODO)

- [ ] **Windows support** qua WSL2 backend
- [ ] **CentOS / RHEL** (yum-based) — nếu BV nào dùng
- [ ] **macOS** (chỉ dev mode, không deploy production)

---

## Files structure hiện tại

```
ehc-installer/
├── README.md
├── PROGRESS.md                    ← file này
├── pyproject.toml
├── Makefile
├── .gitignore
└── src/ehc/
    ├── __init__.py
    ├── cli.py                     ✅ entry typer + dispatch TUI
    ├── tui/
    │   ├── app.py                 ✅ Textual App
    │   ├── styles.tcss            ✅ CSS theme
    │   └── screens/
    │       ├── welcome.py         ✅
    │       ├── detect.py          ✅
    │       ├── install_deps.py    ✅
    │       ├── models.py          ✅
    │       ├── stack_setup.py     ⚠ stub
    │       ├── done.py            ✅
    │       └── help.py            ✅
    ├── commands/
    │   ├── deps.py                ✅ check + install
    │   ├── vllm.py                ✅ install/list/optimize/logs/remove
    │   ├── stack.py               ⚠ stub
    │   └── setup.py               ✅ orchestrator
    └── core/
        ├── detect.py              ✅ OS, GPU, deps detection
        ├── hf_meta.py             ✅ HF API metadata
        ├── optimizer.py           ✅ dynamic VRAM optimizer
        ├── status.py              ✅ aggregate health
        └── install/
            ├── dispatcher.py      ✅ route theo distro
            └── ubuntu.py          ✅ apt install Docker/NVIDIA/Tailscale
```

---

## Quick test (Phase 1 verify)

```bash
cd ehc-installer
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Headless commands
ehc deps check
ehc vllm optimize Qwen/Qwen2.5-VL-3B-Instruct
ehc vllm optimize google/medgemma-1.5-4b-it
ehc status

# Launch TUI
ehc
```

---

## Known issues / TODO debt

1. **`_container_vram_mb` trong `commands/vllm.py`** — chưa cross-ref PID container với nvidia-smi, return 0. Cần dùng `docker inspect` lấy PID rồi map.
2. **HF query `awq_id`** chưa lưu trong ModelMeta — `optimizer._pick_quantization` check `getattr(meta, "awq_id", None)` lúc nào cũng None. Cần thêm field + fetch trong `hf_meta.query()`.
3. **No error handling** cho khi `docker` cmd fail (network, permission). Cần wrap try/except + retry.
4. **Templates Jinja2** chưa tạo. Đang inline strings.
5. **Resume sau reboot** chưa làm.
6. **Tests** chưa có file nào.

---

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-06-26 | Bỏ preset YAML, dùng dynamic optimizer | Adapt mọi GPU mới không cần update file |
| 2026-06-26 | Tách `vllm` ra module riêng | Debug retry độc lập khi fail HF token / OOM |
| 2026-06-26 | Auto-install dep | DevOps team cần workflow 1 lệnh |
| 2026-06-26 | Textual TUI thay questionary | UX cao hơn, panel full-screen, mouse + keyboard |
| 2026-06-26 | Model dynamic input | Không cần biết trước list, optimizer query HF metadata |
