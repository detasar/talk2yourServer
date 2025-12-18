"""
Docker Management Tools

Provides functions to interact with Docker containers.
"""

from utils.shell import run_command


async def list_containers(all_containers: bool = False) -> str:
    """List Docker containers"""
    flag = "-a" if all_containers else ""
    format_str = "table {{.Names}}\t{{.Status}}\t{{.Image}}"

    output, code = await run_command(f'docker ps {flag} --format "{format_str}"')

    title = "ALL CONTAINERS" if all_containers else "RUNNING CONTAINERS"
    return f"{title}\n{'='*40}\n{output}"


async def get_container_stats() -> str:
    """Get resource usage of running containers"""
    output, code = await run_command(
        'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"'
    )
    return f"CONTAINER RESOURCE USAGE\n{'='*40}\n{output}"


async def get_container_logs(container: str, lines: int = 50) -> str:
    """Get logs from a container"""
    output, code = await run_command(f"docker logs --tail {lines} {container} 2>&1")

    if code != 0:
        return f"Error: Container '{container}' not found or not running"

    return f"{container} Logs (last {lines} lines):\n\n{output}"


async def list_images() -> str:
    """List Docker images"""
    output, code = await run_command(
        'docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"'
    )
    return f"DOCKER IMAGES\n{'='*40}\n{output}"


async def start_container(container: str) -> tuple[bool, str]:
    """Start a Docker container"""
    output, code = await run_command(f"docker start {container}")
    if code == 0:
        return True, f"Container '{container}' started"
    return False, f"Error: {output}"


async def stop_container(container: str) -> tuple[bool, str]:
    """Stop a Docker container"""
    output, code = await run_command(f"docker stop {container}")
    if code == 0:
        return True, f"Container '{container}' stopped"
    return False, f"Error: {output}"


async def restart_container(container: str) -> tuple[bool, str]:
    """Restart a Docker container"""
    output, code = await run_command(f"docker restart {container}")
    if code == 0:
        return True, f"Container '{container}' restarted"
    return False, f"Error: {output}"
