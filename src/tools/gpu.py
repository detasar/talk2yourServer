"""
GPU Tools

Provides GPU-specific functions using nvidia-smi.
"""

from utils.shell import run_command


async def is_gpu_available() -> bool:
    """Check if GPU is available"""
    output, code = await run_command("nvidia-smi --query-gpu=name --format=csv,noheader")
    return code == 0 and bool(output.strip())


async def get_gpu_memory_free() -> int:
    """Get free GPU memory in MB"""
    output, code = await run_command(
        "nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits"
    )
    try:
        return int(output.strip())
    except:
        return 0


async def get_gpu_utilization() -> int:
    """Get GPU utilization percentage"""
    output, code = await run_command(
        "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits"
    )
    try:
        return int(output.strip())
    except:
        return 0


async def get_gpu_temperature() -> int:
    """Get GPU temperature in Celsius"""
    output, code = await run_command(
        "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
    )
    try:
        return int(output.strip())
    except (ValueError, AttributeError):
        return -1


async def get_gpu_memory_percent() -> int:
    """Get GPU memory usage percentage"""
    output, code = await run_command(
        "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits"
    )
    try:
        parts = output.strip().split(",")
        if len(parts) >= 2:
            used = int(parts[0].strip())
            total = int(parts[1].strip())
            return int((used / total) * 100)
    except (ValueError, AttributeError, ZeroDivisionError):
        pass
    return -1


async def get_gpu_processes() -> str:
    """Get processes running on GPU"""
    output, code = await run_command(
        "nvidia-smi --query-compute-apps=pid,process_name,used_memory "
        "--format=csv,noheader"
    )
    if not output.strip():
        return "No processes running on GPU"

    lines = ["GPU PROCESSES", "=" * 40]
    for line in output.strip().split('\n'):
        parts = line.split(',')
        if len(parts) >= 3:
            pid, name, mem = [p.strip() for p in parts]
            lines.append(f"  PID {pid}: {name} ({mem} MB)")
        else:
            lines.append(f"  {line}")

    return "\n".join(lines)


async def is_ollama_using_gpu() -> bool:
    """Check if Ollama is currently using GPU"""
    output, code = await run_command(
        "nvidia-smi --query-compute-apps=process_name --format=csv,noheader"
    )
    return "ollama" in output.lower()


async def can_run_ollama() -> tuple[bool, str]:
    """
    Check if Ollama can run (enough GPU memory).
    Returns (can_run, reason)
    """
    free_mem = await get_gpu_memory_free()

    if free_mem < 4000:  # Less than 4GB free
        return False, f"Insufficient GPU memory: {free_mem}MB free (min 4GB required)"

    return True, f"GPU ready: {free_mem}MB free"


async def get_full_nvidia_smi() -> str:
    """Get full nvidia-smi output"""
    output, _ = await run_command("nvidia-smi")
    return output
