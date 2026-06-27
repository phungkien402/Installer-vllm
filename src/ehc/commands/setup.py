"""ehc setup — orchestrate full installation."""
from __future__ import annotations

from rich.console import Console

console = Console()


def run(
    bv_name: str | None,
    models: list[str],
    skip_deps: bool,
    skip_vllm: bool,
    skip_stack: bool,
):
    """Orchestrate: deps → vLLM → stack."""
    console.print("[bold cyan]EHC Installer — full setup[/]\n")

    if not skip_deps:
        console.print("[bold]Phase 1: dependencies[/]")
        from ehc.commands.deps import check, install
        check()
        # Reuse install command (interactive)
        # install([], yes=False)   # caller should run separately if needed
    else:
        console.print("[dim]Skipping deps[/]")

    if not skip_vllm:
        console.print("\n[bold]Phase 2: vLLM models[/]")
        if not models:
            import questionary
            choice = questionary.text(
                "Enter HF model id(s), comma-separated:",
                default="Qwen/Qwen2.5-VL-3B-Instruct,google/medgemma-1.5-4b-it",
            ).ask()
            models = [m.strip() for m in choice.split(",") if m.strip()]
        for m in models:
            console.print(f"  • {m}")
        console.print("[yellow]Use [bold]ehc vllm install <id>[/] cho từng model.[/]")
    else:
        console.print("[dim]Skipping vLLM[/]")

    if not skip_stack:
        console.print("\n[bold]Phase 3: OCR stack[/]")
        if not bv_name:
            import questionary
            bv_name = questionary.text("BV name (Tailscale hostname):", default="ocr-bv").ask()
        console.print(f"[yellow]Use [bold]ehc stack setup --bv-name={bv_name}[/].[/]")
    else:
        console.print("[dim]Skipping stack[/]")

    console.print("\n[green]Setup orchestration complete.[/]")
