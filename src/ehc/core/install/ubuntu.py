"""Ubuntu 22.04 / 24.04 installers."""
from __future__ import annotations

import os
import shutil

from rich.console import Console

from ehc.core.install.dispatcher import run_cmd

console = Console()


def install_basic(name: str, yes: bool) -> None:
    """Cài tool đơn giản qua apt."""
    run_cmd(["apt-get", "update", "-qq"], sudo=True)
    run_cmd(["apt-get", "install", "-y", name], sudo=True)


def install_python(yes: bool) -> None:
    run_cmd(["apt-get", "update", "-qq"], sudo=True)
    run_cmd(["apt-get", "install", "-y", "python3", "python3-pip", "python3-venv"], sudo=True)


def install_docker(yes: bool) -> None:
    """Docker CE official repo."""
    cmds = [
        # remove old conflicting packages (best effort)
        "apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true",
        "apt-get update -qq",
        "apt-get install -y ca-certificates curl gnupg",
        "install -m 0755 -d /etc/apt/keyrings",
        # Add Docker GPG key
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
        "chmod a+r /etc/apt/keyrings/docker.gpg",
        # Add repo
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] '
        'https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" '
        '| tee /etc/apt/sources.list.d/docker.list > /dev/null',
        "apt-get update -qq",
        "apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
        "systemctl enable --now docker",
    ]
    for c in cmds:
        run_cmd(c, sudo=True)

    # Add current user to docker group
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"
    if user != "root":
        run_cmd(["usermod", "-aG", "docker", user], sudo=True, check=False)
        console.print(f"  [yellow]Note:[/] User '{user}' added to docker group. "
                      "Logout/login để áp dụng, hoặc dùng [bold]newgrp docker[/].")


def install_nvidia_toolkit(yes: bool) -> None:
    """NVIDIA Container Toolkit (cần GPU driver đã cài trước)."""
    cmds = [
        # GPG key + repo
        "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey "
        "| gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
        "curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list "
        "| sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' "
        "| tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null",
        "apt-get update -qq",
        "apt-get install -y nvidia-container-toolkit",
        "nvidia-ctk runtime configure --runtime=docker",
        "systemctl restart docker",
    ]
    for c in cmds:
        run_cmd(c, sudo=True)

    # Smoke test
    console.print("  [dim]Smoke test: docker run --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi[/]")
    rc = run_cmd(
        "docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi 2>&1 | head -3",
        check=False
    )
    if rc != 0:
        console.print("  [yellow]⚠ GPU passthrough smoke test failed.[/] Check driver + reboot if needed.")


def install_tailscale(yes: bool) -> None:
    """Tailscale daemon."""
    run_cmd("curl -fsSL https://tailscale.com/install.sh | sh", sudo=True)
    run_cmd(["systemctl", "enable", "--now", "tailscaled"], sudo=True, check=False)
    console.print("  [yellow]Next:[/] Chạy [bold]sudo tailscale up[/] để đăng ký node.")


def hold_nvidia_packages() -> None:
    """Block apt auto-upgrade NVIDIA driver (đã gặp bug mismatch)."""
    pkgs = [
        "nvidia-driver-580-open",
        "nvidia-dkms-580-open",
        "libnvidia-compute-580",
        "libnvidia-common-580",
        "nvidia-utils-580",
        "nvidia-kernel-source-580-open",
        "nvidia-firmware-580",
    ]
    for p in pkgs:
        run_cmd(["apt-mark", "hold", p], sudo=True, check=False)
    console.print("  [green]✓[/] NVIDIA driver packages held (no auto-upgrade).")
