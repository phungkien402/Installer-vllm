"""Detect OS, GPU, drivers, dep status — kết quả nuôi optimizer."""
from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OSInfo:
    family: str           # "ubuntu", "debian", "centos", "windows", "macos", "unknown"
    version: str          # "24.04"
    kernel: str           # "6.8.0-..."
    arch: str             # "x86_64", "aarch64"
    is_supported: bool    # phase 1 chỉ Ubuntu 22.04 + 24.04


@dataclass
class GPUInfo:
    detected: bool
    name: str = ""                      # "NVIDIA GeForce RTX 5080"
    vram_mb: int = 0                    # total
    vram_free_mb: int = 0
    driver_version: str = ""            # "580.159.03"
    cuda_version: str = ""              # "12.8"
    compute_capability: tuple[int, int] = (0, 0)   # (12, 0) for sm_120
    supports_fp8: bool = False          # sm_89+ (Ada/Hopper/Blackwell)
    supports_awq_marlin: bool = False   # sm_80+ (Ampere+)


@dataclass
class DepStatus:
    name: str
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None
    note: str = ""


@dataclass
class Environment:
    os: OSInfo
    gpu: GPUInfo
    deps: list[DepStatus] = field(default_factory=list)


# ---------- OS detection ----------

def _read_os_release() -> dict:
    out: dict[str, str] = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    out[k] = v.strip('"')
    except FileNotFoundError:
        pass
    return out


def detect_os() -> OSInfo:
    sys_name = platform.system().lower()
    if sys_name == "windows":
        return OSInfo(
            family="windows",
            version=platform.release(),
            kernel=platform.version(),
            arch=platform.machine(),
            is_supported=False,
        )
    if sys_name == "darwin":
        return OSInfo("macos", platform.mac_ver()[0], platform.release(),
                      platform.machine(), is_supported=False)

    rel = _read_os_release()
    family = rel.get("ID", "unknown").lower()
    version = rel.get("VERSION_ID", "")
    supported = family == "ubuntu" and version in ("22.04", "24.04")

    return OSInfo(
        family=family,
        version=version,
        kernel=platform.release(),
        arch=platform.machine(),
        is_supported=supported,
    )


# ---------- GPU detection ----------

def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""


def detect_gpu() -> GPUInfo:
    if not shutil.which("nvidia-smi"):
        return GPUInfo(detected=False)

    # Query basic info
    rc, out = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version,compute_cap",
        "--format=csv,noheader,nounits"
    ])
    if rc != 0 or not out.strip():
        return GPUInfo(detected=False)

    line = out.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 5:
        return GPUInfo(detected=False)

    name, vram_total, vram_free, driver, cc = parts
    try:
        major, minor = (int(x) for x in cc.split("."))
    except ValueError:
        major, minor = 0, 0

    # Query CUDA version
    rc, ver_out = _run(["nvidia-smi"])
    m = re.search(r"CUDA Version:\s*([\d.]+)", ver_out)
    cuda = m.group(1) if m else ""

    cc_int = major * 10 + minor
    supports_fp8 = cc_int >= 89        # Ada+
    supports_awq_marlin = cc_int >= 80  # Ampere+

    return GPUInfo(
        detected=True,
        name=name,
        vram_mb=int(vram_total),
        vram_free_mb=int(vram_free),
        driver_version=driver,
        cuda_version=cuda,
        compute_capability=(major, minor),
        supports_fp8=supports_fp8,
        supports_awq_marlin=supports_awq_marlin,
    )


# ---------- Dep detection ----------

def _bin_version(cmd: list[str], pattern: str) -> Optional[str]:
    rc, out = _run(cmd)
    if rc != 0:
        return None
    m = re.search(pattern, out)
    return m.group(1) if m else None


def detect_docker() -> DepStatus:
    path = shutil.which("docker")
    if not path:
        return DepStatus("docker", False)
    ver = _bin_version(["docker", "--version"], r"version\s+([\d.]+)")
    return DepStatus("docker", True, ver, path)


def detect_docker_compose() -> DepStatus:
    rc, out = _run(["docker", "compose", "version"])
    if rc != 0:
        return DepStatus("docker compose", False, note="docker required first")
    m = re.search(r"v([\d.]+)", out)
    return DepStatus("docker compose", True, m.group(1) if m else "unknown")


def detect_nvidia_toolkit() -> DepStatus:
    path = shutil.which("nvidia-ctk")
    if not path:
        return DepStatus("nvidia-container-toolkit", False)
    ver = _bin_version(["nvidia-ctk", "--version"], r"version\s+([\d.]+)")
    return DepStatus("nvidia-container-toolkit", True, ver, path)


def detect_tailscale() -> DepStatus:
    path = shutil.which("tailscale")
    if not path:
        return DepStatus("tailscale", False)
    ver = _bin_version(["tailscale", "version"], r"^([\d.]+)")
    return DepStatus("tailscale", True, ver, path)


def detect_python() -> DepStatus:
    ver = platform.python_version()
    ok = tuple(map(int, ver.split("."))) >= (3, 10)
    return DepStatus("python3", ok, ver, shutil.which("python3"))


def detect_jq_curl_git() -> list[DepStatus]:
    out = []
    for tool in ("jq", "curl", "git"):
        path = shutil.which(tool)
        out.append(DepStatus(tool, bool(path), path=path))
    return out


# ---------- Full sweep ----------

def detect_environment() -> Environment:
    deps: list[DepStatus] = [
        detect_docker(),
        detect_docker_compose(),
        detect_nvidia_toolkit(),
        detect_tailscale(),
        detect_python(),
        *detect_jq_curl_git(),
    ]
    return Environment(
        os=detect_os(),
        gpu=detect_gpu(),
        deps=deps,
    )


def to_dict(env: Environment) -> dict:
    return {
        "os": env.os.__dict__,
        "gpu": env.gpu.__dict__ | {"compute_capability": list(env.gpu.compute_capability)},
        "deps": [d.__dict__ for d in env.deps],
    }


if __name__ == "__main__":
    env = detect_environment()
    print(json.dumps(to_dict(env), indent=2))
