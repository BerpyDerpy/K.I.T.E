"""
skills/system_info.py — System Info Reporter skill for K.I.T.E.

Provides MCP tools to query local machine stats:
  get_os_info, get_cpu_usage, get_memory_usage, get_disk_space

Uses `platform` (stdlib) for OS details and `psutil` for live metrics.
"""

import platform

import psutil
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("System Info Reporter")


# ── Helpers ───────────────────────────────────
def _bytes_to_gb(b: int) -> str:
    """Convert bytes to a human-readable GB string."""
    return f"{b / (1024 ** 3):.2f} GB"


# ── Tools ─────────────────────────────────────
@mcp.tool()
def get_os_info() -> str:
    """Get operating system information including OS name, version, architecture, hostname, and Python version."""
    try:
        info = {
            "System": platform.system(),
            "Release": platform.release(),
            "Version": platform.version(),
            "Machine": platform.machine(),
            "Processor": platform.processor() or "N/A",
            "Hostname": platform.node(),
            "Python": platform.python_version(),
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())
    except Exception as e:
        return f"Failed to retrieve OS info: {e}"


@mcp.tool()
def get_cpu_usage() -> str:
    """Get current CPU usage including core count and per-core utilization percentages."""
    try:
        physical = psutil.cpu_count(logical=False) or "N/A"
        logical = psutil.cpu_count(logical=True)
        overall = psutil.cpu_percent(interval=1)
        per_core = psutil.cpu_percent(interval=0, percpu=True)

        lines = [
            f"Physical cores: {physical}",
            f"Logical cores:  {logical}",
            f"Overall usage:  {overall}%",
            "",
            "Per-core usage:",
        ]
        for i, pct in enumerate(per_core):
            lines.append(f"  Core {i}: {pct}%")

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to retrieve CPU usage: {e}"


@mcp.tool()
def get_memory_usage() -> str:
    """Get current RAM memory usage including total, used, available memory, and usage percentage."""
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        lines = [
            "RAM:",
            f"  Total:     {_bytes_to_gb(mem.total)}",
            f"  Used:      {_bytes_to_gb(mem.used)}",
            f"  Available: {_bytes_to_gb(mem.available)}",
            f"  Usage:     {mem.percent}%",
            "",
            "Swap:",
            f"  Total:     {_bytes_to_gb(swap.total)}",
            f"  Used:      {_bytes_to_gb(swap.used)}",
            f"  Free:      {_bytes_to_gb(swap.free)}",
            f"  Usage:     {swap.percent}%",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to retrieve memory usage: {e}"


@mcp.tool()
def get_disk_space() -> str:
    """Get disk space information for all mounted partitions including total, used, and free space with usage percentages."""
    try:
        partitions = psutil.disk_partitions(all=False)
        lines = []

        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                lines.append(f"Device: {p.device}")
                lines.append(f"  Mountpoint: {p.mountpoint}")
                lines.append(f"  Filesystem: {p.fstype}")
                lines.append(f"  Total:      {_bytes_to_gb(usage.total)}")
                lines.append(f"  Used:       {_bytes_to_gb(usage.used)}")
                lines.append(f"  Free:       {_bytes_to_gb(usage.free)}")
                lines.append(f"  Usage:      {usage.percent}%")
                lines.append("")
            except PermissionError:
                lines.append(f"Device: {p.device}  (permission denied)")
                lines.append("")

        return "\n".join(lines).strip() if lines else "No disk partitions found."
    except Exception as e:
        return f"Failed to retrieve disk space: {e}"


if __name__ == "__main__":
    mcp.run()
