"""Done screen — summary + handover info."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label


class DoneScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="welcome-box"):
                yield Label("[bold green]✅ Setup complete[/]", id="welcome-title")
                yield Label(
                    "\nNext steps:\n"
                    "  • Check [bold]ehc status[/] for health.\n"
                    "  • Get handover doc via [bold]ehc stack info[/].\n"
                    "  • Test endpoints with [bold]ehc stack test[/].\n"
                )
                yield Button("🏠 Back to Home", id="btn-home", variant="primary")
                yield Button("Exit", id="btn-exit")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-home":
                self.app.action_home()
            case "btn-exit":
                self.app.exit()
