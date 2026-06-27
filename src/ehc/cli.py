"""CLI entry — typer dispatch giữa headless command + Textual TUI."""
from __future__ import annotations

import typer
from rich.console import Console

console = Console()

app = typer.Typer(
    name="ehc",
    help="EHC HealthCare AI stack installer (Textual TUI + CLI).",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@app.callback()
def _root(ctx: typer.Context):
    """No subcommand → launch TUI."""
    if ctx.invoked_subcommand is None:
        from ehc.tui.app import EHCInstallerApp
        EHCInstallerApp().run()


# Headless subcommands (for automation / CI)
from ehc.commands import deps as deps_cmd
from ehc.commands import vllm as vllm_cmd
from ehc.commands import stack as stack_cmd

app.add_typer(deps_cmd.app, name="deps", help="System dependencies (headless).")
app.add_typer(vllm_cmd.app, name="vllm", help="vLLM model containers (headless).")
app.add_typer(stack_cmd.app, name="stack", help="OCR stack (headless).")


@app.command()
def tui():
    """Launch Textual TUI explicitly."""
    from ehc.tui.app import EHCInstallerApp
    EHCInstallerApp().run()


@app.command()
def status():
    """Aggregate health status (text)."""
    from ehc.core import status as status_mod
    status_mod.print_all()


@app.command()
def version():
    """Show version."""
    from ehc import __version__
    console.print(f"ehc-installer [bold cyan]{__version__}[/]")


if __name__ == "__main__":
    app()
