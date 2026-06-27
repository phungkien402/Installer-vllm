"""Dispatch install request → đúng installer theo distro."""
from __future__ import annotations

import subprocess
import sys
from typing import Callable

import questionary
from rich.console import Console

from ehc.core import detect

console = Console()


def run_cmd(cmd: list[str] | str, sudo: bool = False, check: bool = True) -> int:
    """Run shell command, in real-time output."""
    if isinstance(cmd, list):
        if sudo and cmd[0] != "sudo":
            cmd = ["sudo"] + cmd
        printable = " ".join(cmd)
    else:
        printable = f"sudo {cmd}" if sudo else cmd
        cmd = ("sudo " if sudo else "") + cmd

    console.print(f"  [dim]$ {printable}[/]")
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), check=check)
        return r.returncode
    except subprocess.CalledProcessError as e:
        console.print(f"  [red]✗ Failed (exit {e.returncode})[/]")
        if check:
            raise typer_exit()
        return e.returncode


def typer_exit():
    import typer
    return typer.Exit(1)


def install_missing(env: detect.Environment, yes: bool = False) -> None:
    """Loop qua deps thiếu, hỏi confirm rồi cài."""
    from ehc.core.install import ubuntu

    missing_installers: list[tuple[str, Callable[[bool], None]]] = []

    for dep in env.deps:
        if dep.installed:
            continue
        if dep.name == "docker":
            missing_installers.append(("Docker CE", ubuntu.install_docker))
        elif dep.name == "nvidia-container-toolkit":
            missing_installers.append(("NVIDIA Container Toolkit", ubuntu.install_nvidia_toolkit))
        elif dep.name == "tailscale":
            missing_installers.append(("Tailscale", ubuntu.install_tailscale))
        elif dep.name == "python3":
            missing_installers.append(("Python 3.10+", ubuntu.install_python))
        elif dep.name in ("jq", "curl", "git"):
            missing_installers.append((dep.name, lambda y, t=dep.name: ubuntu.install_basic(t, y)))

    if not missing_installers:
        console.print("[green]✓ All deps already installed.[/]")
        return

    console.print(f"\n[yellow]Will install:[/] {', '.join(n for n, _ in missing_installers)}")

    if not yes:
        ok = questionary.confirm("Proceed?", default=True).ask()
        if not ok:
            console.print("[red]Aborted.[/]")
            return

    for name, installer in missing_installers:
        console.print(f"\n[bold cyan]Installing {name}...[/]")
        try:
            installer(yes)
        except Exception as e:
            console.print(f"[red]✗ {name} failed:[/] {e}")
            if not questionary.confirm("Continue with next dep?", default=True).ask():
                sys.exit(1)

    console.print("\n[green]✓ Install pass complete.[/]")
    console.print("[yellow]Note:[/] If Docker was newly installed, you may need to relogin (group membership).")


def install_specific(targets: list[str], yes: bool = False) -> None:
    """Cài đặt cụ thể từ list."""
    from ehc.core.install import ubuntu

    map_ = {
        "docker": ubuntu.install_docker,
        "nvidia": ubuntu.install_nvidia_toolkit,
        "nvidia-container-toolkit": ubuntu.install_nvidia_toolkit,
        "tailscale": ubuntu.install_tailscale,
        "python": ubuntu.install_python,
        "python3": ubuntu.install_python,
    }
    for t in targets:
        installer = map_.get(t.lower())
        if not installer:
            console.print(f"[red]Unknown target:[/] {t}")
            continue
        console.print(f"\n[bold cyan]Installing {t}...[/]")
        installer(yes)
