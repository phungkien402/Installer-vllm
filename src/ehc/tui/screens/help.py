"""Help / about screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label


HELP_TEXT = """
[bold cyan]EHC Installer — Help[/]

[bold]Keyboard:[/]
  ↑ ↓       Navigate
  Enter     Select
  Tab       Next field
  Esc       Back
  Q / Ctrl+C  Quit
  F1        This help

[bold]Flow:[/]
  1. Detect — kiểm tra OS, GPU, deps
  2. Install deps — Docker, NVIDIA toolkit, Tailscale
  3. Add models — nhập HF id, optimizer tính args
  4. Install vLLM — pull image + docker run
  5. Stack setup — clone repo OCR + Tailscale Funnel
  6. Done

[bold]Headless CLI:[/]
  ehc deps check
  ehc vllm install <hf-id>
  ehc vllm optimize <hf-id>
  ehc status
"""


class HelpScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="welcome-box"):
                yield Label(HELP_TEXT)
                yield Button("Close", id="btn-close", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.app.pop_screen()
