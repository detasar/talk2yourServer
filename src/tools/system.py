"""
System Information Tools

Provides functions to get system status, GPU, disk, memory, CPU info.
"""

import asyncio
from typing import Optional

from utils.shell import run_command


async def get_gpu_info(detail: str = "summary") -> str:
    """
    Get GPU information

    detail: "summary" | "full" | "processes" | "memory" | "temp"
    """
    if detail == "full":
        output, _ = await run_command("nvidia-smi")
        return output

    if detail == "processes":
        output, _ = await run_command("nvidia-smi pmon -c 1")
        return output

    if detail == "memory":
        output, _ = await run_command(
            "nvidia-smi --query-gpu=memory.used,memory.total,memory.free "
            "--format=csv,noheader,nounits"
        )
        if output:
            parts = output.split(",")
            if len(parts) >= 3:
                used, total, free = [p.strip() for p in parts]
                return (
                    f"GPU Memory:\n"
                    f"  Used: {used} MB\n"
                    f"  Total: {total} MB\n"
                    f"  Free: {free} MB"
                )
        return output

    if detail == "temp":
        output, _ = await run_command(
            "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
        )
        if output:
            return f"GPU Temperature: {output}C"
        return output

    # Summary (default)
    output, _ = await run_command(
        "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu "
        "--format=csv,noheader,nounits"
    )
    if output:
        parts = output.split(",")
        if len(parts) >= 5:
            name, util, mem_used, mem_total, temp = [p.strip() for p in parts]
            return (
                f"GPU: {name}\n"
                f"  Utilization: {util}%\n"
                f"  Memory: {mem_used}/{mem_total} MB\n"
                f"  Temperature: {temp}C"
            )
    return output


async def get_disk_usage(detail: str = "summary") -> str:
    """
    Get disk usage information

    detail: "summary" | "full" | "large"
    """
    if detail == "full":
        output, _ = await run_command("df -h")
        return output

    if detail == "large":
        output, _ = await run_command(
            "du -h --max-depth=1 ~ 2>/dev/null | sort -hr | head -15"
        )
        return f"Largest Directories (~):\n{output}"

    # Summary - just root partition
    output, _ = await run_command("df -h / | tail -1")
    if output:
        parts = output.split()
        if len(parts) >= 5:
            return (
                f"Disk Usage (/):\n"
                f"  Total: {parts[1]}\n"
                f"  Used: {parts[2]}\n"
                f"  Free: {parts[3]}\n"
                f"  Usage: {parts[4]}"
            )
    return output


async def get_memory_usage() -> str:
    """Get RAM usage"""
    output, _ = await run_command("free -h")
    return f"Memory Usage:\n{output}"


async def get_cpu_usage() -> str:
    """Get CPU usage"""
    output, _ = await run_command(
        "top -bn1 | head -5"
    )
    return f"CPU Status:\n{output}"


async def get_uptime() -> str:
    """Get system uptime"""
    output, _ = await run_command("uptime -p")
    return f"System Uptime: {output}"


async def get_network_info() -> str:
    """Get network information"""
    # Get Tailscale IP
    ts_output, _ = await run_command("tailscale ip -4 2>/dev/null || echo 'Tailscale not running'")

    # Get local IPs
    local_output, _ = await run_command("hostname -I")

    return (
        f"Network Info:\n"
        f"  Tailscale IP: {ts_output}\n"
        f"  Local IPs: {local_output}"
    )


async def get_processes(sort_by: str = "cpu", limit: int = 10) -> str:
    """Get top processes"""
    if sort_by == "memory":
        cmd = f"ps aux --sort=-%mem | head -{limit + 1}"
    else:
        cmd = f"ps aux --sort=-%cpu | head -{limit + 1}"

    output, _ = await run_command(cmd)
    return f"Top {'Memory' if sort_by == 'memory' else 'CPU'} Processes:\n{output}"


async def get_full_status() -> str:
    """Get comprehensive system status"""

    # Run all checks in parallel
    gpu_task = get_gpu_info("summary")
    disk_task = get_disk_usage("summary")
    mem_task = run_command("free -h | grep Mem")
    uptime_task = run_command("uptime -p")
    load_task = run_command("cat /proc/loadavg")

    gpu, disk, (mem, _), (uptime, _), (load, _) = await asyncio.gather(
        gpu_task, disk_task, mem_task, uptime_task, load_task
    )

    # Parse memory
    mem_parts = mem.split() if mem else []
    mem_info = f"{mem_parts[2]}/{mem_parts[1]}" if len(mem_parts) >= 3 else "N/A"

    # Parse load
    load_parts = load.split() if load else []
    load_info = f"{load_parts[0]}, {load_parts[1]}, {load_parts[2]}" if len(load_parts) >= 3 else "N/A"

    return (
        f"SYSTEM STATUS\n"
        f"{'='*30}\n\n"
        f"Uptime: {uptime}\n"
        f"Load Average: {load_info}\n"
        f"Memory: {mem_info}\n\n"
        f"{gpu}\n\n"
        f"{disk}"
    )


async def get_conda_envs() -> str:
    """List conda environments"""
    output, _ = await run_command("conda env list")
    return f"Conda Environments:\n{output}"


async def get_ollama_models() -> str:
    """List Ollama models"""
    output, _ = await run_command("ollama list 2>/dev/null || echo 'Ollama not running'")
    return f"Ollama Models:\n{output}"


# === Numeric getters for alerting ===

async def get_disk_percent() -> int:
    """Get root disk usage percentage as integer"""
    output, code = await run_command("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    try:
        return int(output.strip())
    except (ValueError, AttributeError):
        return -1


async def get_memory_percent() -> int:
    """Get RAM usage percentage as integer"""
    output, code = await run_command(
        "free | grep Mem | awk '{printf \"%.0f\", $3/$2 * 100}'"
    )
    try:
        return int(output.strip())
    except (ValueError, AttributeError):
        return -1


async def get_cpu_percent() -> int:
    """Get CPU usage percentage as integer"""
    output, code = await run_command(
        "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
    )
    try:
        return int(float(output.strip()))
    except (ValueError, AttributeError):
        return -1
