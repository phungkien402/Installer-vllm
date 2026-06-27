"""ehc stack subcommands — OCR + auth proxy + Tailscale Funnel."""
from __future__ import annotations

import typer
from rich.console import Console

from ehc.core.stack import StackConfig, setup_full, print_handover

console = Console()
app = typer.Typer(help="OCR + auth proxy + Tailscale Funnel.")


@app.command("setup")
def setup_cmd(
    bv_name: str = typer.Option(..., "--bv-name", help="BV name (Tailscale hostname)."),
    repo: str = typer.Option("https://github.com/phungkien402/ocr.git", "--repo"),
    branch: str = typer.Option("sub_main", "--branch"),
    workdir: str = typer.Option("~/OCR_PHR", "--workdir"),
    enable_funnel: bool = typer.Option(True, "--enable-funnel/--no-funnel"),
    qwen_url: str = typer.Option("http://localhost:8080", "--qwen-url"),
    medgemma_url: str = typer.Option("http://localhost:8082", "--medgemma-url"),
):
    """Clone OCR repo + generate compose + start services + Tailscale Funnel."""
    cfg = StackConfig(
        bv_name=bv_name,
        repo_url=repo,
        branch=branch,
        workdir=workdir,
        enable_funnel=enable_funnel,
        qwen_url=qwen_url,
        medgemma_url=medgemma_url,
    )
    summary = setup_full(cfg)
    print_handover(summary)


@app.command("info")
def info_cmd(
    workdir: str = typer.Option("~/OCR_PHR", "--workdir"),
):
    """Print URLs + tokens (handover format)."""
    import os
    from pathlib import Path
    wd = Path(os.path.expanduser(workdir))
    summary: dict[str, str] = {"workdir": str(wd)}

    ocr_env = wd / "OCR_server" / ".env"
    if ocr_env.exists():
        for line in ocr_env.read_text().splitlines():
            if line.startswith("OCR_API_KEY="):
                summary["OCR_API_KEY"] = line.split("=", 1)[1]

    proxy_env = wd / ".vllm_proxy.env"
    if proxy_env.exists():
        for line in proxy_env.read_text().splitlines():
            if line.startswith("VLLM_PROXY_KEY="):
                summary["VLLM_PROXY_KEY"] = line.split("=", 1)[1]

    # Tailscale URL
    import subprocess
    r = subprocess.run(["tailscale", "funnel", "status"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "ts.net" in line and "https://" in line:
            summary["public_url"] = line.strip().split()[0]
            break

    summary.setdefault("bv_name", "?")
    print_handover(summary)


@app.command("test")
def test_cmd(
    workdir: str = typer.Option("~/OCR_PHR", "--workdir"),
):
    """Smoke test endpoints."""
    import os
    import subprocess
    from pathlib import Path
    import httpx

    wd = Path(os.path.expanduser(workdir))
    console.print("[bold]Smoke test[/]")

    # OCR health
    try:
        r = httpx.get("http://localhost:7005/health", timeout=5)
        console.print(f"  OCR /health: [green]{r.status_code}[/]  {r.text[:120]}")
    except Exception as e:
        console.print(f"  OCR /health: [red]✗ {e}[/]")

    # Auth proxy health
    try:
        r = httpx.get("http://localhost:8081/health", timeout=5)
        console.print(f"  Proxy /health: [green]{r.status_code}[/]  {r.text[:120]}")
    except Exception as e:
        console.print(f"  Proxy /health: [red]✗ {e}[/]")

    # OCR extract with test image
    test_img = wd / "test_images" / "bb.jpg"
    if test_img.exists():
        ocr_env = wd / "OCR_server" / ".env"
        key = None
        if ocr_env.exists():
            for line in ocr_env.read_text().splitlines():
                if line.startswith("OCR_API_KEY="):
                    key = line.split("=", 1)[1]
                    break
        if key:
            try:
                with open(test_img, "rb") as f:
                    r = httpx.post(
                        "http://localhost:7005/v1/extract",
                        headers={"X-API-Key": key},
                        files={"file": f},
                        timeout=30,
                    )
                console.print(f"  OCR /v1/extract: [green]{r.status_code}[/]  {r.text[:200]}")
            except Exception as e:
                console.print(f"  OCR /v1/extract: [red]✗ {e}[/]")


@app.command("restart")
def restart_cmd(
    service: str = typer.Argument(None, help="Service name (omit for all)."),
    workdir: str = typer.Option("~/OCR_PHR", "--workdir"),
):
    """Restart stack service via docker compose."""
    import os
    import subprocess
    wd = os.path.expanduser(workdir)
    args = ["docker", "compose", "restart"]
    if service:
        args.append(service)
    subprocess.run(args, cwd=wd)


@app.command("logs")
def logs_cmd(
    service: str = typer.Argument("ocr-server"),
    follow: bool = typer.Option(False, "-f", "--follow"),
    tail: int = typer.Option(50, "--tail"),
    workdir: str = typer.Option("~/OCR_PHR", "--workdir"),
):
    """Tail stack logs."""
    import os
    import subprocess
    wd = os.path.expanduser(workdir)
    args = ["docker", "compose", "logs", "--tail", str(tail)]
    if follow:
        args.append("-f")
    args.append(service)
    subprocess.run(args, cwd=wd)


@app.command("destroy")
def destroy_cmd(
    workdir: str = typer.Option("~/OCR_PHR", "--workdir"),
    keep_data: bool = typer.Option(True, "--keep-data/--purge-data"),
):
    """Tear down stack."""
    import os
    import subprocess
    wd = os.path.expanduser(workdir)
    args = ["docker", "compose", "down"]
    if not keep_data:
        args.append("-v")
    subprocess.run(args, cwd=wd)
    subprocess.run(["pkill", "-f", "vllm_auth_proxy.py"], capture_output=True)
    console.print("[green]✓ Stack torn down.[/]")
