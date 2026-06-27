"""Detect screen — show OS, GPU, deps status."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from ehc.core import detect


class DetectScreen(Screen):
    """Show environment detection."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("n", "next", "Next"),
    ]

    def __init__(self, start_flow: bool = False):
        super().__init__()
        self.start_flow = start_flow
        self.env: detect.Environment | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="section"):
            yield Label("[bold cyan]System Detection[/]", classes="title")
            yield Static(id="os-info")
            yield Static(id="gpu-info")
        with Vertical(classes="section"):
            yield Label("[bold]Dependencies[/]", classes="title")
            yield DataTable(id="deps-table")
        with Horizontal():
            yield Button("Refresh", id="btn-refresh", variant="primary")
            yield Button(
                "Next: install deps →" if self.start_flow else "Back",
                id="btn-next",
                variant="success" if self.start_flow else "default",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._populate()

    def action_refresh(self) -> None:
        self._populate()

    def action_next(self) -> None:
        self._goto_next()

    def _populate(self) -> None:
        self.env = detect.detect_environment()
        env = self.env

        # OS info
        os_str = (
            f"[bold]OS:[/]      {env.os.family} {env.os.version} ({env.os.arch})\n"
            f"[bold]Kernel:[/]  {env.os.kernel}\n"
            f"[bold]Support:[/] "
            + ("[green]✓ supported[/]" if env.os.is_supported else "[red]✗ unsupported[/]")
        )
        self.query_one("#os-info", Static).update(os_str)

        # GPU info
        if env.gpu.detected:
            cc = env.gpu.compute_capability
            gpu_str = (
                f"[bold]GPU:[/]    {env.gpu.name}\n"
                f"[bold]VRAM:[/]   {env.gpu.vram_mb} MB total, "
                f"{env.gpu.vram_free_mb} MB free\n"
                f"[bold]Driver:[/] {env.gpu.driver_version}  |  "
                f"[bold]CUDA:[/] {env.gpu.cuda_version}  |  "
                f"sm_{cc[0]}{cc[1]}\n"
                f"[bold]FP8:[/] {'✓' if env.gpu.supports_fp8 else '✗'}   "
                f"[bold]AWQ marlin:[/] {'✓' if env.gpu.supports_awq_marlin else '✗'}"
            )
        else:
            gpu_str = "[red]✗ No NVIDIA GPU detected[/]"
        self.query_one("#gpu-info", Static).update(gpu_str)

        # Deps table
        table = self.query_one("#deps-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Tool", "Status", "Version", "Path")
        for d in env.deps:
            status = "[green]✓[/]" if d.installed else "[red]✗[/]"
            table.add_row(d.name, status, d.version or "-", d.path or "-")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-refresh":
                self._populate()
            case "btn-next":
                self._goto_next()

    def _goto_next(self) -> None:
        if not self.env:
            return
        missing = [d.name for d in self.env.deps if not d.installed]
        if self.start_flow and missing:
            from ehc.tui.screens.install_deps import InstallDepsScreen
            self.app.push_screen(InstallDepsScreen(missing=missing))
        elif self.start_flow:
            from ehc.tui.screens.models import ModelsScreen
            self.app.push_screen(ModelsScreen())
        else:
            self.app.pop_screen()
