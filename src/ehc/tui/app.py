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
        """Pop về Welcome screen — giữ ở top stack."""
        from ehc.tui.screens.welcome import WelcomeScreen

        # Pop hết screen ở trên Welcome. Welcome luôn ở stack[1] (stack[0] là default).
        # Phòng trường hợp Welcome bị pop nhầm → push fresh.
        while len(self.screen_stack) > 2:
            self.pop_screen()

        # Nếu vì lý do gì đó current screen không phải Welcome → switch
        if not isinstance(self.screen, WelcomeScreen):
            self.switch_screen(WelcomeScreen())

    def action_help(self) -> None:
        from ehc.tui.screens.help import HelpScreen
        self.push_screen(HelpScreen())
