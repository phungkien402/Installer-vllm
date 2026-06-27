"""Install deps screen — checkboxes + live log."""
from __future__ import annotations

import asyncio
import subprocess

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Label, RichLog, Static


DEP_INSTALLERS = {
    "docker": "install_docker",
    "nvidia-container-toolkit": "install_nvidia_toolkit",
    "tailscale": "install_tailscale",
    "python3": "install_python",
}


class InstallDepsScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("a", "select_all", "Select all"),
    ]

    def __init__(self, missing: list[str]):
        super().__init__()
        self.missing = missing
        self.checkboxes: dict[str, Checkbox] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="section"):
            yield Label("[bold cyan]Install Dependencies[/]", classes="title")
            yield Static(f"Missing: [yellow]{', '.join(self.missing)}[/]")
            with Vertical(id="checkboxes-box"):
                for name in self.missing:
                    if name in DEP_INSTALLERS:
                        cb = Checkbox(name, value=True, id=f"cb-{name}")
                        self.checkboxes[name] = cb
                        yield cb

        with Vertical(classes="section"):
            yield Label("[bold]Install Log[/]", classes="title")
            yield RichLog(id="install-log", highlight=True, markup=True)

        with Horizontal():
            yield Button("Install selected", id="btn-install", variant="success")
            yield Button("Skip → Next", id="btn-skip", variant="primary")
            yield Button("Back", id="btn-back")
        yield Footer()

    def action_select_all(self) -> None:
        for cb in self.checkboxes.values():
            cb.value = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-install":
                self.run_worker(self._do_install(), exclusive=True)
            case "btn-skip":
                self._goto_next()
            case "btn-back":
                self.app.pop_screen()

    async def _do_install(self) -> None:
        log = self.query_one("#install-log", RichLog)
        from ehc.core.install import ubuntu

        selected = [name for name, cb in self.checkboxes.items() if cb.value]
        if not selected:
            log.write("[yellow]Nothing selected.[/]")
            return

        for name in selected:
            log.write(f"\n[bold cyan]→ Installing {name}...[/]")
            fn_name = DEP_INSTALLERS.get(name)
            if not fn_name:
                log.write(f"  [yellow]No installer for {name}[/]")
                continue
            fn = getattr(ubuntu, fn_name, None)
            if not fn:
                log.write(f"  [red]Installer fn not found: {fn_name}[/]")
                continue
            try:
                await asyncio.to_thread(fn, True)
                log.write(f"  [green]✓ {name} done[/]")
            except Exception as e:
                log.write(f"  [red]✗ {name} failed: {e}[/]")

        log.write("\n[bold green]All selected deps processed.[/]")

    def _goto_next(self) -> None:
        from ehc.tui.screens.models import ModelsScreen
        self.app.push_screen(ModelsScreen())
