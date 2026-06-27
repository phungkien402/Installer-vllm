"""Aggregate health status."""
from __future__ import annotations

import subprocess

import httpx
from rich.console import Console
from rich.table import Table

console = Console()


def print_all():
    """In tổng hợp: deps, vLLM containers, stack endpoints."""
    from ehc.core import detect

    env = detect.detect_environment()

    # Deps quick
    t = Table(title="Status")
    t.add_column("Component")
    t.add_column("Status")
    t.add_column("Note")

    t.add_row("OS", env.os.family + " " + env.os.version,
              "✓" if env.os.is_supported else "unsupported")
    if env.gpu.detected:
        t.add_row("GPU", env.gpu.name,
                  f"{env.gpu.vram_mb} MB, free {env.gpu.vram_free_mb} MB")
    else:
        t.add_row("GPU", "[red]not detected[/]", "")

    for d in env.deps:
        t.add_row(d.name, "[green]✓[/]" if d.installed else "[red]✗[/]", d.version or "-")

    console.print(t)

    # vLLM containers
    r = subprocess.run(
        ["docker", "ps", "--filter", "name=vllm-", "--format",
         "{{.Names}} {{.Status}}"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        console.print("\n[bold]vLLM containers[/]")
        if not r.stdout.strip():
            console.print("  [yellow]none[/]")
        else:
            for line in r.stdout.strip().splitlines():
                console.print(f"  {line}")

    # Stack endpoints
    console.print("\n[bold]Endpoints[/]")
    _check_endpoint("OCR /health", "http://localhost:7005/health")
    _check_endpoint("Auth proxy /health", "http://localhost:8081/health")


def _check_endpoint(label: str, url: str):
    try:
        r = httpx.get(url, timeout=3)
        if r.status_code == 200:
            console.print(f"  [green]✓[/] {label}: {url}")
        else:
            console.print(f"  [yellow]?[/] {label}: HTTP {r.status_code}")
    except Exception as e:
        console.print(f"  [red]✗[/] {label}: {e.__class__.__name__}")
