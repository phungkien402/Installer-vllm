"""Stack setup screen — clone OCR repo + Tailscale Funnel, all in TUI."""
from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Switch

from ehc.core import stack as stack_mod


class StackSetupScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("h", "app.home", "Home"),
    ]

    def __init__(self):
        super().__init__()
        self.summary: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="section"):
            yield Label("[bold cyan]OCR Stack Setup[/]", classes="title")
            yield Label("Clone OCR repo → generate compose → start services → Tailscale Funnel")

            yield Label("BV name (Tailscale hostname):")
            yield Input(placeholder="ocr-bv-noibai", id="inp-bv-name")

            yield Label("Repo URL:")
            yield Input(value=stack_mod.OCR_REPO_DEFAULT, id="inp-repo")

            yield Label("Branch:")
            yield Input(value=stack_mod.OCR_BRANCH_DEFAULT, id="inp-branch")

            yield Label("Working directory:")
            yield Input(value=stack_mod.WORKDIR_DEFAULT, id="inp-workdir")

            with Horizontal():
                yield Label("Enable Tailscale Funnel:")
                yield Switch(value=True, id="sw-funnel")

        with Vertical(classes="section"):
            yield Label("[bold]Log[/]", classes="title")
            yield RichLog(id="stack-log", highlight=True, markup=True)

        with Horizontal():
            yield Button("🏠 Home", id="btn-home")
            yield Button("Run setup", id="btn-setup", variant="success")
            yield Button("Back", id="btn-back")
            yield Button("Show handover info", id="btn-info", variant="primary")
            yield Button("Finish →", id="btn-finish")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-home":
                self.app.action_home()
            case "btn-setup":
                self.run_worker(self._do_setup(), exclusive=True)
            case "btn-back":
                self.app.pop_screen()
            case "btn-info":
                self._show_info()
            case "btn-finish":
                from ehc.tui.screens.done import DoneScreen
                self.app.push_screen(DoneScreen())

    async def _do_setup(self) -> None:
        log = self.query_one("#stack-log", RichLog)
        bv_name = self.query_one("#inp-bv-name", Input).value.strip()
        if not bv_name:
            log.write("[red]✗ BV name required[/]")
            return
        repo = self.query_one("#inp-repo", Input).value.strip()
        branch = self.query_one("#inp-branch", Input).value.strip()
        workdir = self.query_one("#inp-workdir", Input).value.strip()
        funnel = self.query_one("#sw-funnel", Switch).value

        cfg = stack_mod.StackConfig(
            bv_name=bv_name, repo_url=repo, branch=branch,
            workdir=workdir, enable_funnel=funnel,
        )

        log.write(f"[bold cyan]→ Setup '{bv_name}'[/]")
        try:
            summary = await asyncio.to_thread(stack_mod.setup_full, cfg)
        except Exception as e:
            log.write(f"[red]✗ Setup failed: {e}[/]")
            return

        self.summary = summary
        log.write("\n[bold green]✓ Stack setup complete[/]")
        log.write(f"  workdir:        {summary.get('workdir')}")
        if "public_url" in summary:
            log.write(f"  public URL:     {summary['public_url']}")
        log.write(f"  OCR API key:    [yellow]{summary.get('OCR_API_KEY', '?')[:16]}...[/]")
        log.write(f"  CDSS proxy key: [yellow]{summary.get('VLLM_PROXY_KEY', '?')[:16]}...[/]")
        log.write("[dim]Use 'Show handover info' for full keys.[/]")

    def _show_info(self) -> None:
        log = self.query_one("#stack-log", RichLog)
        if not self.summary:
            log.write("[yellow]No setup summary yet. Run setup first.[/]")
            return
        s = self.summary
        log.write("\n[bold]═ Handover info ═[/]")
        log.write(f"BV name:        {s.get('bv_name')}")
        log.write(f"Workdir:        {s.get('workdir')}")
        if "public_url" in s:
            log.write(f"OCR endpoint:   {s['public_url']}/v1/extract")
            log.write(f"CDSS endpoint:  {s['public_url'].rstrip('/')}:8443/v1/chat/completions")
        log.write(f"OCR_API_KEY:    [yellow]{s.get('OCR_API_KEY', '?')}[/]")
        log.write(f"VLLM_PROXY_KEY: [yellow]{s.get('VLLM_PROXY_KEY', '?')}[/]")
