"""
Server Management Tools

Collection of tools for system monitoring and management.
"""

from .system import (
    get_gpu_info,
    get_disk_usage,
    get_memory_usage,
    get_cpu_usage,
    get_uptime,
    get_network_info,
    get_processes,
    get_full_status,
    get_conda_envs,
    get_ollama_models,
    get_disk_percent,
    get_memory_percent,
    get_cpu_percent
)

from .gpu import (
    is_gpu_available,
    get_gpu_memory_free,
    get_gpu_utilization,
    get_gpu_temperature,
    get_gpu_memory_percent,
    get_gpu_processes,
    is_ollama_using_gpu,
    can_run_ollama,
    get_full_nvidia_smi
)

from .docker import (
    list_containers,
    get_container_stats,
    get_container_logs,
    list_images,
    start_container,
    stop_container,
    restart_container
)

from .services import (
    get_service_status,
    get_all_services_status,
    start_service,
    stop_service,
    restart_service,
    get_service_logs,
    get_monitoring_status,
    start_monitoring,
    stop_monitoring
)

from .screenshot import (
    capture_screenshot,
    generate_gpu_chart,
    generate_system_chart,
    generate_disk_chart
)

__all__ = [
    # System
    "get_gpu_info", "get_disk_usage", "get_memory_usage", "get_cpu_usage",
    "get_uptime", "get_network_info", "get_processes", "get_full_status",
    "get_conda_envs", "get_ollama_models", "get_disk_percent",
    "get_memory_percent", "get_cpu_percent",
    # GPU
    "is_gpu_available", "get_gpu_memory_free", "get_gpu_utilization",
    "get_gpu_temperature", "get_gpu_memory_percent", "get_gpu_processes",
    "is_ollama_using_gpu", "can_run_ollama", "get_full_nvidia_smi",
    # Docker
    "list_containers", "get_container_stats", "get_container_logs",
    "list_images", "start_container", "stop_container", "restart_container",
    # Services
    "get_service_status", "get_all_services_status", "start_service",
    "stop_service", "restart_service", "get_service_logs",
    "get_monitoring_status", "start_monitoring", "stop_monitoring",
    # Screenshot
    "capture_screenshot", "generate_gpu_chart", "generate_system_chart",
    "generate_disk_chart"
]
