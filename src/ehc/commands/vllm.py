"""ehc vllm subcommands — manage vLLM containers."""
from __future__ import annotations

import os
import subprocess

import typer
from rich.console import Console
from rich.table import Table

from ehc.core import detect, hf_meta, optimizer

console = Console()
app = typer.Typer(help="vLLM model containers.")


def _container_name(hf_id: str) -> str:
    """Tên container deterministic từ HF id. vd 'google/medgemma-1.5-4b-it' → 'vllm-medgemma-1-5-4b-it'."""
    base = hf_id.split("/")[-1].lower()
    safe = "".join(c if c.isalnum() else "-" for c in base).strip("-")
    return f"vllm-{safe}"[:60]


def _docker_args_from_plan(name: str, port: int, plan: optimizer.VLLMArgs, hf_env: str | None) -> list[str]:
    """Build docker run args list."""
    args = [
        "docker", "run", "-d",
        "--name", name,
        "--gpus", "all",
        "--restart", "unless-stopped",
        "-p", f"{port}:8000",
        "-v", f"{os.path.expanduser('~/.cache/huggingface')}:/root/.cache/huggingface",
        "--ipc=host",
    ]
    if hf_env and os.path.isfile(hf_env):
        args += ["--env-file", hf_env]

    args += ["vllm/vllm-openai:latest"]
    args += ["--model", plan.model]
    if plan.served_model_name:
        args += ["--served-model-name", plan.served_model_name]
    if plan.quantization:
        args += ["--quantization", plan.quantization]
    args += ["--dtype", plan.dtype]
    args += ["--gpu-memory-utilization", str(plan.gpu_memory_utilization)]
    args += ["--max-model-len", str(plan.max_model_len)]
    if plan.enforce_eager:
        args += ["--enforce-eager"]
    if plan.limit_mm_per_prompt:
        args += ["--limit-mm-per-prompt", plan.limit_mm_per_prompt]
    return args


@app.command("optimize")
def optimize_cmd(
    hf_id: list[str] = typer.Argument(..., help="HF model id(s)."),
    hf_token: str = typer.Option(None, "--hf-token", envvar="HF_TOKEN", help="HuggingFace token."),
):
    """In ra plan optimizer (không apply)."""
    gpu = detect.detect_gpu()
    if not gpu.detected:
        console.print("[red]✗ No GPU detected.[/]")
        raise typer.Exit(1)

    metas = []
    for hf in hf_id:
        meta = hf_meta.query(hf, token=hf_token)
        if not meta.exists:
            console.print(f"[red]✗ Model not found:[/] {hf}")
            continue
        if meta.gated and not meta.accessible:
            console.print(f"[red]✗ Gated model, no access:[/] {hf}")
            console.print("  Accept license + set HF_TOKEN")
            continue
        metas.append(meta)

    if not metas:
        raise typer.Exit(1)

    plans = optimizer.optimize_many(metas, gpu)

    for meta, plan in zip(metas, plans):
        _print_plan(meta, plan, gpu)


def _print_plan(meta: hf_meta.ModelMeta, plan: optimizer.VLLMArgs, gpu: detect.GPUInfo) -> None:
    t = Table(title=f"Plan — {meta.hf_id}", show_header=False)
    t.add_column(style="dim")
    t.add_column()
    t.add_row("HF id", plan.model)
    if plan.served_model_name:
        t.add_row("Served as", plan.served_model_name)
    t.add_row("Params", f"{meta.params_b}B")
    t.add_row("Multimodal", "✓" if meta.is_multimodal else "✗")
    t.add_row("Native context", str(meta.native_context))
    t.add_row("Quantization", plan.quantization or "none")
    t.add_row("dtype", plan.dtype)
    t.add_row("gpu_memory_utilization", str(plan.gpu_memory_utilization))
    t.add_row("max_model_len", str(plan.max_model_len))
    t.add_row("enforce_eager", "true" if plan.enforce_eager else "false")
    if plan.limit_mm_per_prompt:
        t.add_row("limit_mm_per_prompt", plan.limit_mm_per_prompt)
    t.add_row("Estimated VRAM", f"{plan.estimated_vram_mb} MB / {gpu.vram_mb} MB total")
    console.print(t)

    console.print("[dim]Rationale:[/]")
    for r in plan.rationale:
        console.print(f"  • {r}")
    console.print()


@app.command("install")
def install_cmd(
    hf_id: str = typer.Argument(..., help="HF model id."),
    port: int = typer.Option(0, help="Host port to bind (auto-assign if 0)."),
    hf_token: str = typer.Option(None, "--hf-token", envvar="HF_TOKEN"),
    hf_env: str = typer.Option(None, "--hf-env", help="Path to .env file with HF_TOKEN."),
    apply: bool = typer.Option(False, "--apply", help="Skip confirmation."),
):
    """Cài 1 model vLLM với optimizer args."""
    gpu = detect.detect_gpu()
    if not gpu.detected:
        console.print("[red]✗ No GPU detected.[/]")
        raise typer.Exit(1)

    meta = hf_meta.query(hf_id, token=hf_token)
    if not meta.exists:
        console.print(f"[red]✗ Model not found:[/] {hf_id}")
        raise typer.Exit(1)
    if meta.gated and not meta.accessible:
        console.print(f"[red]✗ Gated model. Visit https://huggingface.co/{hf_id} to accept license.[/]")
        console.print("Set HF_TOKEN env var hoặc dùng --hf-token / --hf-env.")
        raise typer.Exit(1)

    # Compute plan considering existing vLLM containers
    existing = _list_running_vllm()
    used_vram = sum(c["vram_mb"] for c in existing)
    available_vram = gpu.vram_mb - used_vram

    # Adjust GPU info to reflect available
    gpu_for_planning = detect.GPUInfo(**{**gpu.__dict__, "vram_mb": available_vram})
    plan = optimizer.optimize_one(meta, gpu_for_planning, vram_budget_mb=available_vram)

    _print_plan(meta, plan, gpu)

    if not apply:
        import questionary
        ok = questionary.confirm("Apply this plan?", default=True).ask()
        if not ok:
            console.print("[yellow]Aborted.[/]")
            raise typer.Exit()

    # Determine port
    if port == 0:
        port = _next_free_port(8080)

    name = _container_name(hf_id)

    # Stop existing container with same name if any
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)

    args = _docker_args_from_plan(name, port, plan, hf_env)
    console.print(f"[dim]$ {' '.join(args)}[/]\n")
    r = subprocess.run(args)
    if r.returncode != 0:
        console.print(f"[red]✗ docker run failed.[/]")
        raise typer.Exit(r.returncode)

    console.print(f"[green]✓ Container '{name}' starting on port {port}.[/]")
    console.print(f"  Tail logs: [bold]ehc vllm logs {name}[/]")


@app.command("list")
def list_cmd():
    """List running vLLM containers."""
    rows = _list_running_vllm()
    if not rows:
        console.print("[yellow]No vllm containers running.[/]")
        return
    t = Table(title="vLLM Containers")
    t.add_column("Name")
    t.add_column("Port")
    t.add_column("Model")
    t.add_column("VRAM (MB)")
    for c in rows:
        t.add_row(c["name"], str(c["port"]), c.get("model", "?"), str(c.get("vram_mb", "?")))
    console.print(t)


@app.command("remove")
def remove_cmd(
    name: str = typer.Argument(..., help="Container name."),
):
    """Stop + remove vLLM container."""
    subprocess.run(["docker", "stop", name])
    subprocess.run(["docker", "rm", name])
    console.print(f"[green]✓ Removed {name}.[/]")


@app.command("logs")
def logs_cmd(
    name: str = typer.Argument(..., help="Container name."),
    follow: bool = typer.Option(False, "-f", "--follow"),
    tail: int = typer.Option(50, help="Lines to show."),
):
    """Tail container logs."""
    args = ["docker", "logs"]
    if follow:
        args.append("-f")
    args += ["--tail", str(tail), name]
    subprocess.run(args)


@app.command("doctor")
def doctor_cmd():
    """Check vLLM stack health + VRAM usage."""
    rows = _list_running_vllm()
    gpu = detect.detect_gpu()
    console.print(f"GPU: {gpu.name} {gpu.vram_mb} MB total, {gpu.vram_free_mb} MB free\n")
    if not rows:
        console.print("[yellow]No vllm containers.[/]")
        return
    for c in rows:
        console.print(f"  {c['name']}: port {c['port']}, ~{c.get('vram_mb', '?')} MB")


# ---------- Helpers ----------

def _list_running_vllm() -> list[dict]:
    """Parse docker ps cho vllm-* containers."""
    r = subprocess.run(
        ["docker", "ps", "--filter", "name=vllm-", "--format",
         "{{.Names}}\t{{.Ports}}\t{{.Image}}"],
        capture_output=True, text=True,
    )
    rows = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[0]
        ports = parts[1]
        port = 0
        for p in ports.split(","):
            if "->8000" in p:
                # 0.0.0.0:8080->8000/tcp
                try:
                    port = int(p.split(":")[1].split("->")[0])
                except (IndexError, ValueError):
                    pass
                break
        vram = _container_vram_mb(name)
        rows.append({"name": name, "port": port, "vram_mb": vram})
    return rows


def _container_vram_mb(name: str) -> int:
    """Get VRAM dùng bởi container qua nvidia-smi pmon-like query."""
    # Try via docker exec + nvidia-smi if available in container, else 0
    # For now, parse nvidia-smi cmd output across all processes
    r = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,used_memory",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True,
    )
    # Map pid → container name not trivial; placeholder 0
    # TODO: dùng `docker inspect` lấy PID → cross-ref
    return 0


def _next_free_port(start: int = 8080) -> int:
    """Find next free TCP port from start (8080..8100)."""
    import socket
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free port in 8080-8129")
