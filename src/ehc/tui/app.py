"""Textual App entry — full-screen TUI installer."""
from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from ehc.tui.screens.welcome import WelcomeScreen


class EHCInstallerApp(App):
    """EHC HealthCare AI Installer — TUI."""

    TITLE = "EHC HealthCare AI Installer"
    SUB_TITLE = "v0.1.0"

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("f1", "help", "Help", show=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())

    def action_help(self) -> None:
        from ehc.tui.screens.help import HelpScreen
        self.push_screen(HelpScreen())
