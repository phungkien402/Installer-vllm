"""Welcome screen — splash + main menu."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static


WELCOME_TEXT = """
[bold cyan]EHC HealthCare AI Installer[/]

Cài đặt tự động:
  • System dependencies (Docker, NVIDIA, Tailscale)
  • vLLM models (Qwen, MedGemma, custom)
  • OCR stack (ocr-server, auth proxy, Tailscale Funnel)

Target: Ubuntu 22.04 / 24.04, GPU NVIDIA
"""


class WelcomeScreen(Screen):
    """Splash + entry point."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="welcome-box"):
                yield Label(WELCOME_TEXT, id="welcome-title")
                yield Button("Start setup", id="btn-start", variant="success")
                yield Button("Check environment only", id="btn-check", variant="primary")
                yield Button("vLLM management", id="btn-vllm", variant="primary")
                yield Button("Quit", id="btn-quit", variant="error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from ehc.tui.screens.detect import DetectScreen
        from ehc.tui.screens.models import ModelsScreen

        match event.button.id:
            case "btn-start":
                self.app.push_screen(DetectScreen(start_flow=True))
            case "btn-check":
                self.app.push_screen(DetectScreen(start_flow=False))
            case "btn-vllm":
                self.app.push_screen(ModelsScreen())
            case "btn-quit":
                self.app.exit()
