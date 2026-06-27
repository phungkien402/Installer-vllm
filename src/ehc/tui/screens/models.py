"""Models screen — input HF id, view optimizer plan, install."""
from __future__ import annotations

import asyncio
import os
import subprocess

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, RichLog, Static

from ehc.commands import vllm as vllm_cmd
from ehc.core import detect, hf_meta, optimizer


SUGGESTED_MODELS = [
    "Qwen/Qwen2.5-VL-3B-Instruct",
    "google/medgemma-1.5-4b-it",
    "google/gemma-3-4b-it",
    "meta-llama/Llama-3.2-3B-Instruct",
    "microsoft/Phi-3.5-mini-instruct",
]


class ModelsScreen(Screen):
    """Add models, see VRAM plan, install."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("a", "add_focus", "Add field"),
    ]

    def __init__(self):
        super().__init__()
        self.queue: list[str] = []
        self.plans: dict[str, optimizer.VLLMArgs] = {}
        self.metas: dict[str, hf_meta.ModelMeta] = {}
        self.gpu: detect.GPUInfo | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="section"):
            yield Label("[bold cyan]vLLM Models[/]", classes="title")
            yield Static(id="gpu-summary")

            with Horizontal():
                yield Input(
                    placeholder="HuggingFace model id (vd: google/medgemma-1.5-4b-it)",
                    id="model-input",
                )
                yield Button("Add", id="btn-add", variant="primary")

            yield Static(
                "[dim]Suggested: " + "  ".join(SUGGESTED_MODELS) + "[/]",
                id="suggestions",
            )

        with Vertical(classes="section"):
            yield Label("[bold]Planned models (queue)[/]", classes="title")
            yield DataTable(id="queue-table")

        with Vertical(classes="section"):
            yield Label("[bold]Install log[/]", classes="title")
            yield RichLog(id="model-log", highlight=True, markup=True)

        with Horizontal():
            yield Button("Recompute plan", id="btn-replan", variant="primary")
            yield Button("Install all", id="btn-install", variant="success")
            yield Button("Clear queue", id="btn-clear")
            yield Button("Next →", id="btn-next")
        yield Footer()

    def on_mount(self) -> None:
        self.gpu = detect.detect_gpu()
        if self.gpu.detected:
            self.query_one("#gpu-summary", Static).update(
                f"[bold]GPU:[/] {self.gpu.name}  "
                f"[bold]VRAM:[/] {self.gpu.vram_mb} MB  "
                f"[bold]Free:[/] {self.gpu.vram_free_mb} MB"
            )
        else:
            self.query_one("#gpu-summary", Static).update("[red]No GPU detected[/]")

        table = self.query_one("#queue-table", DataTable)
        table.add_columns("Model", "Params", "Quant", "VRAM (MB)", "max_len", "Eager")

    def action_add_focus(self) -> None:
        self.query_one("#model-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-add":
                self._add_model()
            case "btn-replan":
                self.run_worker(self._recompute(), exclusive=True)
            case "btn-install":
                self.run_worker(self._install_all(), exclusive=True)
            case "btn-clear":
                self.queue.clear()
                self.plans.clear()
                self.metas.clear()
                self.query_one("#queue-table", DataTable).clear()
                self.query_one("#model-log", RichLog).write("[yellow]Queue cleared.[/]")
            case "btn-next":
                from ehc.tui.screens.stack_setup import StackSetupScreen
                self.app.push_screen(StackSetupScreen())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "model-input":
            self._add_model()

    def _add_model(self) -> None:
        input_w = self.query_one("#model-input", Input)
        hf_id = input_w.value.strip()
        if not hf_id:
            return
        if hf_id in self.queue:
            self.query_one("#model-log", RichLog).write(f"[yellow]Already queued: {hf_id}[/]")
            return
        self.queue.append(hf_id)
        input_w.value = ""
        self.run_worker(self._fetch_meta_and_replan(hf_id), exclusive=False)

    async def _fetch_meta_and_replan(self, hf_id: str) -> None:
        log = self.query_one("#model-log", RichLog)
        log.write(f"[dim]Querying HF for {hf_id}...[/]")
        try:
            meta = await asyncio.to_thread(hf_meta.query, hf_id)
        except Exception as e:
            log.write(f"  [red]HF query failed: {e}[/]")
            self.queue.remove(hf_id)
            return

        if not meta.exists:
            log.write(f"  [red]Model not found: {hf_id}[/]")
            self.queue.remove(hf_id)
            return
        if meta.gated and not meta.accessible:
            log.write(f"  [yellow]⚠ License-gated. Set HF_TOKEN to access.[/]")
            # keep in queue — user can set token later

        self.metas[hf_id] = meta
        await self._recompute()

    async def _recompute(self) -> None:
        if not self.gpu or not self.gpu.detected:
            return

        # Only use metas we have
        metas = [self.metas[h] for h in self.queue if h in self.metas]
        if not metas:
            return

        plans = await asyncio.to_thread(optimizer.optimize_many, metas, self.gpu)
        # Map back to hf_id ordering
        for hf_id, plan in zip([m.hf_id for m in metas], plans):
            self.plans[hf_id] = plan

        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#queue-table", DataTable)
        table.clear()
        for hf_id in self.queue:
            plan = self.plans.get(hf_id)
            meta = self.metas.get(hf_id)
            if not plan or not meta:
                table.add_row(hf_id, "?", "?", "?", "?", "?")
                continue
            table.add_row(
                hf_id,
                f"{meta.params_b}B",
                plan.quantization or "none",
                str(plan.estimated_vram_mb),
                str(plan.max_model_len),
                "yes" if plan.enforce_eager else "no",
            )

    async def _install_all(self) -> None:
        log = self.query_one("#model-log", RichLog)
        if not self.queue:
            log.write("[yellow]Queue is empty.[/]")
            return

        log.write("\n[bold cyan]Installing models...[/]")
        port = 8080
        for hf_id in self.queue:
            plan = self.plans.get(hf_id)
            if not plan:
                log.write(f"  [red]No plan for {hf_id}, skip.[/]")
                continue
            log.write(f"\n[bold]→ {hf_id}[/]")
            log.write(f"  port={port}  vram={plan.estimated_vram_mb}MB  quant={plan.quantization or 'none'}")

            name = vllm_cmd._container_name(hf_id)
            args = vllm_cmd._docker_args_from_plan(
                name, port, plan,
                hf_env=os.path.expanduser("~/OCR_PHR/.hf_env") if os.path.isfile(
                    os.path.expanduser("~/OCR_PHR/.hf_env")
                ) else None,
            )

            # Stop existing
            await asyncio.to_thread(subprocess.run, ["docker", "rm", "-f", name], capture_output=True)
            # Run
            try:
                r = await asyncio.to_thread(subprocess.run, args, capture_output=True, text=True)
                if r.returncode == 0:
                    log.write(f"  [green]✓ {name} started on :{port}[/]")
                else:
                    log.write(f"  [red]✗ docker run failed:[/] {r.stderr.strip()[:200]}")
            except Exception as e:
                log.write(f"  [red]✗ {e}[/]")
            port += 1

        log.write("\n[bold green]Install pass done.[/]")
        log.write("[dim]Use [bold]docker logs <name>[/] để theo dõi model load.[/]")
