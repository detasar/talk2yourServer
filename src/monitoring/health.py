"""
Health Check HTTP Server

Provides an HTTP endpoint for external monitoring tools (UptimeRobot, Prometheus, etc.)
"""

import asyncio
import json
import logging
import time
from aiohttp import web
from typing import Optional, Any

from config import config
from db import db

logger = logging.getLogger(__name__)


class HealthChecker:
    """HTTP server for health checks"""

    def __init__(self, port: int = 8765):
        self.port = port
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.start_time: float = time.time()
        self.last_message_time: float = 0
        self.message_count: int = 0
        self.error_count: int = 0

    def record_message(self) -> None:
        """Record that a message was processed"""
        self.last_message_time = time.time()
        self.message_count += 1

    def record_error(self) -> None:
        """Record that an error occurred"""
        self.error_count += 1

    async def _check_database(self) -> dict[str, Any]:
        """Check database connectivity"""
        try:
            if db.pool:
                async with db.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return {"status": "healthy", "connected": True}
            else:
                return {"status": "disconnected", "connected": False}
        except Exception as e:
            return {"status": "error", "connected": False, "error": str(e)}

    async def _check_telegram(self) -> dict[str, Any]:
        """Check if bot is receiving messages (based on last message time)"""
        if self.last_message_time == 0:
            return {"status": "no_messages_yet", "healthy": True}

        time_since_last = time.time() - self.last_message_time

        # If no message in 24 hours, might be concerning but not unhealthy
        if time_since_last > 86400:
            return {
                "status": "idle",
                "healthy": True,
                "last_message_ago_seconds": int(time_since_last)
            }

        return {
            "status": "active",
            "healthy": True,
            "last_message_ago_seconds": int(time_since_last)
        }

    async def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status"""
        uptime = time.time() - self.start_time

        # Gather health checks
        db_health = await self._check_database()
        telegram_health = await self._check_telegram()

        # Overall health
        is_healthy = db_health.get("connected", False) or db_health.get("status") == "disconnected"

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "uptime_seconds": int(uptime),
            "message_count": self.message_count,
            "error_count": self.error_count,
            "checks": {
                "database": db_health,
                "telegram": telegram_health
            },
            "config": {
                "alert_enabled": config.alert_enabled,
                "allowed_users_count": len(config.allowed_users),
                "admin_users_count": len(config.admin_users)
            }
        }

    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint"""
        status = await self.get_health_status()
        http_status = 200 if status["status"] == "healthy" else 503

        return web.json_response(status, status=http_status)

    async def handle_ready(self, request: web.Request) -> web.Response:
        """Handle /ready endpoint (Kubernetes-style readiness)"""
        status = await self.get_health_status()

        if status["status"] == "healthy":
            return web.Response(text="OK", status=200)
        else:
            return web.Response(text="NOT READY", status=503)

    async def handle_live(self, request: web.Request) -> web.Response:
        """Handle /live endpoint (Kubernetes-style liveness)"""
        # Simple liveness - if we can respond, we're alive
        return web.Response(text="OK", status=200)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint (Prometheus format)"""
        uptime = time.time() - self.start_time

        metrics = [
            f"# HELP telegram_bot_uptime_seconds Time since bot started",
            f"# TYPE telegram_bot_uptime_seconds gauge",
            f"telegram_bot_uptime_seconds {int(uptime)}",
            "",
            f"# HELP telegram_bot_messages_total Total messages processed",
            f"# TYPE telegram_bot_messages_total counter",
            f"telegram_bot_messages_total {self.message_count}",
            "",
            f"# HELP telegram_bot_errors_total Total errors",
            f"# TYPE telegram_bot_errors_total counter",
            f"telegram_bot_errors_total {self.error_count}",
            "",
            f"# HELP telegram_bot_alert_enabled Alert system enabled",
            f"# TYPE telegram_bot_alert_enabled gauge",
            f"telegram_bot_alert_enabled {1 if config.alert_enabled else 0}",
        ]

        return web.Response(
            text="\n".join(metrics),
            content_type="text/plain"
        )

    async def start(self) -> bool:
        """Start the health check HTTP server"""
        try:
            self.app = web.Application()
            self.app.router.add_get("/health", self.handle_health)
            self.app.router.add_get("/ready", self.handle_ready)
            self.app.router.add_get("/live", self.handle_live)
            self.app.router.add_get("/metrics", self.handle_metrics)

            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await self.site.start()

            self.start_time = time.time()
            logger.info(f"Health check server started on port {self.port}")
            logger.info(f"Endpoints: /health, /ready, /live, /metrics")
            return True

        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            return False

    async def stop(self) -> None:
        """Stop the health check HTTP server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")


# Global health checker instance
health_checker = HealthChecker(port=config.health_check_port)
