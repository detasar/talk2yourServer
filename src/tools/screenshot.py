"""
Screenshot and Visual Metrics Tools

Provides screenshot capture and metric visualization capabilities.
"""

import asyncio
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional, BinaryIO

from utils.shell import run_command

logger = logging.getLogger(__name__)


async def capture_screenshot() -> Optional[bytes]:
    """
    Capture a screenshot of the desktop.
    Requires X server running or Xvfb for headless.
    Returns PNG image bytes or None if failed.
    """
    try:
        # Check if DISPLAY is set
        output, code = await run_command("echo $DISPLAY")
        display = output.strip()

        if not display:
            # Try common display values
            display = ":0"

        # Use scrot or import (ImageMagick) for screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        # Try scrot first
        _, code = await run_command(f"DISPLAY={display} scrot -o {tmp_path} 2>/dev/null")

        if code != 0:
            # Fallback to ImageMagick import
            _, code = await run_command(
                f"DISPLAY={display} import -window root {tmp_path} 2>/dev/null"
            )

        if code != 0:
            logger.warning("Screenshot capture failed - no display or tools available")
            return None

        # Read the image
        with open(tmp_path, "rb") as f:
            data = f.read()

        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)

        return data

    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return None


async def generate_gpu_chart() -> Optional[bytes]:
    """
    Generate a GPU metrics chart using matplotlib.
    Returns PNG image bytes.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np

        # Get current GPU metrics
        from tools.gpu import (
            get_gpu_utilization, get_gpu_memory_percent,
            get_gpu_temperature
        )

        util = await get_gpu_utilization()
        mem_pct = await get_gpu_memory_percent()
        temp = await get_gpu_temperature()

        # Create figure with dark theme
        plt.style.use('dark_background')
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))

        # GPU Utilization gauge
        ax1 = axes[0]
        colors = ['#2ecc71' if util < 70 else '#f39c12' if util < 90 else '#e74c3c']
        ax1.barh([0], [util], color=colors, height=0.5)
        ax1.barh([0], [100 - util], left=[util], color='#2c3e50', height=0.5)
        ax1.set_xlim(0, 100)
        ax1.set_yticks([])
        ax1.set_xlabel('Usage (%)')
        ax1.set_title(f'GPU: {util}%', fontsize=14, fontweight='bold')

        # Memory gauge
        ax2 = axes[1]
        mem_color = '#2ecc71' if mem_pct < 70 else '#f39c12' if mem_pct < 90 else '#e74c3c'
        ax2.barh([0], [mem_pct], color=mem_color, height=0.5)
        ax2.barh([0], [100 - mem_pct], left=[mem_pct], color='#2c3e50', height=0.5)
        ax2.set_xlim(0, 100)
        ax2.set_yticks([])
        ax2.set_xlabel('VRAM (%)')
        ax2.set_title(f'VRAM: {mem_pct}%', fontsize=14, fontweight='bold')

        # Temperature gauge
        ax3 = axes[2]
        temp_pct = min(temp, 100)  # Cap at 100 for display
        temp_color = '#2ecc71' if temp < 60 else '#f39c12' if temp < 80 else '#e74c3c'
        ax3.barh([0], [temp_pct], color=temp_color, height=0.5)
        ax3.barh([0], [100 - temp_pct], left=[temp_pct], color='#2c3e50', height=0.5)
        ax3.set_xlim(0, 100)
        ax3.set_yticks([])
        ax3.set_xlabel('Temperature (C)')
        ax3.set_title(f'Temperature: {temp}C', fontsize=14, fontweight='bold')

        plt.suptitle('GPU Status', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()

        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='#1a1a2e', edgecolor='none')
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    except ImportError:
        logger.warning("matplotlib not available for chart generation")
        return None
    except Exception as e:
        logger.error(f"GPU chart error: {e}")
        return None


async def generate_system_chart() -> Optional[bytes]:
    """
    Generate a system overview chart.
    Returns PNG image bytes.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        from tools.system import get_disk_percent, get_memory_percent, get_cpu_percent
        from tools.gpu import get_gpu_utilization

        # Get metrics
        cpu = await get_cpu_percent()
        mem = await get_memory_percent()
        disk = await get_disk_percent()
        gpu = await get_gpu_utilization()

        # Create pie charts
        plt.style.use('dark_background')
        fig, axes = plt.subplots(2, 2, figsize=(10, 10))

        def make_donut(ax, value, title, threshold_warn=70, threshold_crit=90):
            """Create a donut chart"""
            if value < 0:
                value = 0

            color = '#2ecc71' if value < threshold_warn else '#f39c12' if value < threshold_crit else '#e74c3c'
            sizes = [value, 100 - value]
            colors = [color, '#2c3e50']

            wedges, _ = ax.pie(sizes, colors=colors, startangle=90,
                              wedgeprops=dict(width=0.3, edgecolor='#1a1a2e'))
            ax.set_title(title, fontsize=14, fontweight='bold', pad=10)

            # Add center text
            ax.text(0, 0, f'{value}%', ha='center', va='center',
                   fontsize=24, fontweight='bold', color='white')

        make_donut(axes[0, 0], cpu, 'CPU')
        make_donut(axes[0, 1], mem, 'RAM')
        make_donut(axes[1, 0], disk, 'Disk')
        make_donut(axes[1, 1], gpu, 'GPU')

        plt.suptitle('System Status', fontsize=18, fontweight='bold', y=0.98)
        plt.tight_layout()

        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='#1a1a2e', edgecolor='none')
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    except ImportError:
        logger.warning("matplotlib not available for chart generation")
        return None
    except Exception as e:
        logger.error(f"System chart error: {e}")
        return None


async def generate_disk_chart() -> Optional[bytes]:
    """
    Generate a disk usage chart.
    Returns PNG image bytes.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Get disk info
        output, _ = await run_command("df -h --output=target,pcent,size,used | tail -n +2 | head -5")

        if not output.strip():
            return None

        mounts = []
        percents = []
        sizes = []

        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 4:
                mount = parts[0]
                pct = int(parts[1].replace('%', ''))
                size = parts[2]
                used = parts[3]

                # Skip tiny partitions
                if 'M' in size and float(size.replace('M', '').replace('G', '')) < 500:
                    continue

                mounts.append(f"{mount}\n({used}/{size})")
                percents.append(pct)

        if not mounts:
            return None

        # Create chart
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))

        colors = ['#2ecc71' if p < 70 else '#f39c12' if p < 90 else '#e74c3c' for p in percents]

        bars = ax.barh(range(len(mounts)), percents, color=colors, height=0.6)
        ax.set_yticks(range(len(mounts)))
        ax.set_yticklabels(mounts)
        ax.set_xlim(0, 100)
        ax.set_xlabel('Usage (%)')
        ax.set_title('Disk Usage', fontsize=16, fontweight='bold')

        # Add percentage labels
        for bar, pct in zip(bars, percents):
            ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                   f'{pct}%', va='center', fontweight='bold')

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='#1a1a2e', edgecolor='none')
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    except ImportError:
        logger.warning("matplotlib not available for chart generation")
        return None
    except Exception as e:
        logger.error(f"Disk chart error: {e}")
        return None
