"""
Systemd Watchdog Support

Provides periodic notifications to systemd when running as a service.
"""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import sdnotify, but make it optional
try:
    import sdnotify
    SDNOTIFY_AVAILABLE = True
except ImportError:
    SDNOTIFY_AVAILABLE = False
    sdnotify = None


class SystemdWatchdog:
    """Manages systemd watchdog notifications"""

    def __init__(self):
        self.notifier: Optional["sdnotify.SystemdNotifier"] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.watchdog_usec: int = 0

    def _get_watchdog_interval(self) -> float:
        """Get watchdog interval from environment (in seconds)"""
        watchdog_usec = os.environ.get("WATCHDOG_USEC", "0")
        try:
            self.watchdog_usec = int(watchdog_usec)
            if self.watchdog_usec > 0:
                return (self.watchdog_usec / 1_000_000) / 2
        except ValueError:
            pass
        return 0

    def start(self) -> bool:
        """Start the watchdog notification loop"""
        if not SDNOTIFY_AVAILABLE:
            logger.info("sdnotify not available, watchdog disabled")
            return False

        interval = self._get_watchdog_interval()
        if interval <= 0:
            logger.info("Not running under systemd watchdog")
            return False

        self.notifier = sdnotify.SystemdNotifier()
        self.running = True
        self.task = asyncio.create_task(self._notify_loop(interval))
        logger.info(f"Systemd watchdog started (interval: {interval:.1f}s)")
        return True

    def stop(self) -> None:
        """Stop the watchdog notification loop"""
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None

    def notify_ready(self) -> None:
        """Notify systemd that the service is ready"""
        if self.notifier:
            self.notifier.notify("READY=1")
            logger.info("Notified systemd: READY")

    def notify_stopping(self) -> None:
        """Notify systemd that the service is stopping"""
        if self.notifier:
            self.notifier.notify("STOPPING=1")
            logger.info("Notified systemd: STOPPING")

    def notify_status(self, status: str) -> None:
        """Notify systemd with a status message"""
        if self.notifier:
            self.notifier.notify(f"STATUS={status}")

    def notify_watchdog(self) -> None:
        """Send watchdog keepalive"""
        if self.notifier:
            self.notifier.notify("WATCHDOG=1")

    async def _notify_loop(self, interval: float) -> None:
        """Background loop to send watchdog notifications"""
        while self.running:
            try:
                self.notify_watchdog()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog notification error: {e}")
                await asyncio.sleep(interval)


# Global watchdog instance
watchdog = SystemdWatchdog()
