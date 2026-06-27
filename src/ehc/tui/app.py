"""Textual App entry — full-screen TUI installer."""
from __future__ import annotations

from textual.app import App
from textual.binding import Binding


class EHCInstallerApp(App):
    """EHC HealthCare AI Installer — TUI."""

    TITLE = "EHC HealthCare AI Installer"
    SUB_TITLE = "v0.1.0"

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("h", "home", "Home", show=True),
        Binding("f1", "help", "Help", show=True),
    ]

    def on_mount(self) -> None:
        from ehc.tui.screens.welcome import WelcomeScreen
        self.push_screen(WelcomeScreen())

    def action_home(self) -> None:
        """Pop về Welcome screen (luôn ở dưới cùng stack)."""
        # Pop hết các screen cho đến khi chỉ còn 1 (Welcome)
        while len(self.screen_stack) > 1:
            self.pop_screen()

    def action_help(self) -> None:
        from ehc.tui.screens.help import HelpScreen
        self.push_screen(HelpScreen())
