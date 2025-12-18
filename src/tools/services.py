"""
Service Management Tools

Handles starting, stopping, and checking status of services.
"""

import asyncio
from typing import Literal

from config import MANAGED_SERVICES
from utils.shell import run_command


async def get_service_status(service_name: str) -> tuple[str, bool]:
    """
    Get status of a service.
    Returns (status_message, is_running)
    """
    if service_name not in MANAGED_SERVICES:
        return f"Unknown service: {service_name}", False

    service = MANAGED_SERVICES[service_name]

    if service["type"] == "docker":
        output, code = await run_command(
            f"docker inspect -f '{{{{.State.Running}}}}' {service['name']} 2>/dev/null"
        )
        is_running = output.strip().lower() == "true"
        status = "Running" if is_running else "Stopped"
        return f"{service_name}: {status}", is_running

    elif service["type"] == "systemd":
        output, code = await run_command(
            f"systemctl is-active {service['name']} 2>/dev/null"
        )
        is_running = output.strip() == "active"
        status = "Running" if is_running else "Stopped"
        return f"{service_name}: {status}", is_running

    return f"{service_name}: Unknown type", False


async def get_all_services_status() -> str:
    """Get status of all managed services"""

    tasks = [
        get_service_status(name)
        for name in MANAGED_SERVICES.keys()
    ]

    results = await asyncio.gather(*tasks)

    lines = ["SERVICE STATUS", "=" * 30, ""]

    docker_services = []
    systemd_services = []

    for (name, service), (status, is_running) in zip(MANAGED_SERVICES.items(), results):
        icon = "🟢" if is_running else "🔴"
        line = f"{icon} {status}"

        if service["type"] == "docker":
            docker_services.append(line)
        else:
            systemd_services.append(line)

    if systemd_services:
        lines.append("Systemd:")
        lines.extend(f"  {s}" for s in systemd_services)
        lines.append("")

    if docker_services:
        lines.append("Docker:")
        lines.extend(f"  {s}" for s in docker_services)

    return "\n".join(lines)


async def start_service(service_name: str) -> tuple[bool, str]:
    """
    Start a service.
    Returns (success, message)
    """
    if service_name not in MANAGED_SERVICES:
        return False, f"Unknown service: {service_name}"

    service = MANAGED_SERVICES[service_name]

    if service["type"] == "docker":
        output, code = await run_command(f"docker start {service['name']}")
        if code == 0:
            return True, f"{service_name} started"
        return False, f"Error: {output}"

    elif service["type"] == "systemd":
        # Special handling for some services
        if service_name == "ollama":
            output, code = await run_command("ollama serve &")
            await asyncio.sleep(2)
            return True, f"{service_name} started"

        output, code = await run_command(f"sudo systemctl start {service['name']}")
        if code == 0:
            return True, f"{service_name} started"
        return False, f"Error: {output}"

    return False, "Unknown service type"


async def stop_service(service_name: str) -> tuple[bool, str]:
    """
    Stop a service.
    Returns (success, message)
    """
    if service_name not in MANAGED_SERVICES:
        return False, f"Unknown service: {service_name}"

    service = MANAGED_SERVICES[service_name]

    if service["type"] == "docker":
        output, code = await run_command(f"docker stop {service['name']}")
        if code == 0:
            return True, f"{service_name} stopped"
        return False, f"Error: {output}"

    elif service["type"] == "systemd":
        # Special handling for ollama
        if service_name == "ollama":
            output, code = await run_command("pkill ollama")
            return True, f"{service_name} stopped"

        output, code = await run_command(f"sudo systemctl stop {service['name']}")
        if code == 0:
            return True, f"{service_name} stopped"
        return False, f"Error: {output}"

    return False, "Unknown service type"


async def restart_service(service_name: str) -> tuple[bool, str]:
    """
    Restart a service.
    Returns (success, message)
    """
    success, msg = await stop_service(service_name)
    if not success and "Unknown" not in msg:
        return False, msg

    await asyncio.sleep(1)

    success, msg = await start_service(service_name)
    if success:
        return True, f"{service_name} restarted"
    return False, msg


async def get_service_logs(service_name: str, lines: int = 50) -> str:
    """Get logs for a service"""
    if service_name not in MANAGED_SERVICES:
        return f"Unknown service: {service_name}"

    service = MANAGED_SERVICES[service_name]

    if service["type"] == "docker":
        output, _ = await run_command(f"docker logs --tail {lines} {service['name']} 2>&1")
        return f"{service_name} Logs (last {lines} lines):\n\n{output}"

    elif service["type"] == "systemd":
        output, _ = await run_command(f"journalctl -u {service['name']} -n {lines} --no-pager")
        return f"{service_name} Logs (last {lines} lines):\n\n{output}"

    return "Unknown service type"


async def get_monitoring_status() -> str:
    """Get monitoring stack status"""
    services = ["prometheus", "grafana", "node-exporter", "nvidia-exporter"]

    tasks = [get_service_status(s) for s in services]
    results = await asyncio.gather(*tasks)

    lines = ["MONITORING STATUS", "=" * 30, ""]

    all_running = True
    for (status, is_running) in results:
        icon = "🟢" if is_running else "🔴"
        lines.append(f"{icon} {status}")
        if not is_running:
            all_running = False

    if all_running:
        lines.append("")
        lines.append("Grafana: http://SERVER_IP:3000")
        lines.append("Prometheus: http://SERVER_IP:9090")

    return "\n".join(lines)


async def start_monitoring() -> str:
    """Start monitoring stack"""
    output, code = await run_command(
        "cd ~/monitoring && docker compose up -d",
        timeout=60
    )
    if code == 0:
        return "Monitoring stack started"
    return f"Error: {output}"


async def stop_monitoring() -> str:
    """Stop monitoring stack"""
    output, code = await run_command(
        "cd ~/monitoring && docker compose down",
        timeout=60
    )
    if code == 0:
        return "Monitoring stack stopped"
    return f"Error: {output}"
