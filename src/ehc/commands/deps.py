"""ehc deps subcommands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ehc.core import detect

console = Console()
app = typer.Typer(help="System dependencies (Docker, NVIDIA, Tailscale).")


@app.command("check")
def check():
    """Phát hiện môi trường + báo dep còn thiếu."""
    env = detect.detect_environment()

    # OS
    table = Table(title="Environment", show_header=False)
    table.add_column(style="dim")
    table.add_column()
    table.add_row("OS", f"{env.os.family} {env.os.version} ({env.os.arch})")
    table.add_row("Kernel", env.os.kernel)
    table.add_row("Supported", "✓" if env.os.is_supported else "✗ (phase 1: Ubuntu 22.04/24.04)")
    console.print(table)

    # GPU
    gpu_t = Table(title="GPU", show_header=False)
    gpu_t.add_column(style="dim")
    gpu_t.add_column()
    if env.gpu.detected:
        gpu_t.add_row("Name", env.gpu.name)
        gpu_t.add_row("VRAM", f"{env.gpu.vram_mb} MB (free {env.gpu.vram_free_mb} MB)")
        gpu_t.add_row("Driver", env.gpu.driver_version)
        gpu_t.add_row("CUDA", env.gpu.cuda_version)
        cc = env.gpu.compute_capability
        gpu_t.add_row("Compute capability", f"sm_{cc[0]}{cc[1]}")
        gpu_t.add_row("FP8 support", "✓" if env.gpu.supports_fp8 else "✗")
        gpu_t.add_row("AWQ marlin", "✓" if env.gpu.supports_awq_marlin else "✗")
    else:
        gpu_t.add_row("Status", "[red]NOT DETECTED[/] (nvidia-smi missing or no GPU)")
    console.print(gpu_t)

    # Deps
    deps_t = Table(title="Dependencies")
    deps_t.add_column("Tool")
    deps_t.add_column("Status")
    deps_t.add_column("Version")
    for d in env.deps:
        status = "[green]✓[/]" if d.installed else "[red]✗[/]"
        deps_t.add_row(d.name, status, d.version or "-")
    console.print(deps_t)

    missing = [d.name for d in env.deps if not d.installed]
    if missing:
        console.print(f"\n[yellow]Missing:[/] {', '.join(missing)}")
        console.print("Install with: [bold]ehc deps install[/]")
    else:
        console.print("\n[green]All dependencies ready.[/]")


@app.command("install")
def install(
    target: list[str] = typer.Argument(None, help="Specific dep(s) to install."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmations."),
):
    """Cài deps thiếu (Ubuntu 22.04/24.04 only ở phase 1)."""
    from ehc.core.install import dispatcher

    env = detect.detect_environment()

    if not env.os.is_supported:
        console.print(f"[red]✗ OS not supported:[/] {env.os.family} {env.os.version}")
        console.print("Phase 1 chỉ hỗ trợ Ubuntu 22.04 / 24.04")
        raise typer.Exit(1)

    if target:
        dispatcher.install_specific(target, yes=yes)
    else:
        dispatcher.install_missing(env, yes=yes)
