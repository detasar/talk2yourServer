"""
Ollama Client

Handles communication with local Ollama instance.
"""

import asyncio
import json
from typing import AsyncIterator, Optional

import httpx

from config import config
from tools.gpu import get_gpu_memory_free, is_ollama_using_gpu


class OllamaClient:
    """Client for local Ollama instance"""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or config.ollama_url
        self.model = model or config.default_ollama_model
        self.timeout = httpx.Timeout(120.0, connect=10.0)

    async def is_available(self) -> tuple[bool, str]:
        """
        Check if Ollama is available and has enough GPU memory.
        Returns (available, reason)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False, "Ollama not responding"
        except Exception as e:
            return False, f"Ollama connection failed: {str(e)}"

        # Check GPU memory
        free_mem = await get_gpu_memory_free()
        if free_mem < 4000:  # Less than 4GB
            return False, f"Insufficient GPU memory: {free_mem}MB free"

        return True, "Ollama ready"

    async def list_models(self) -> list[str]:
        """List available models"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []

    async def generate(
        self,
        prompt: str,
        system: str = None,
        model: str = None
    ) -> str:
        """Generate a response (non-streaming)"""
        model = model or self.model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Ollama error: {str(e)}"

    async def generate_stream(
        self,
        prompt: str,
        system: str = None,
        model: str = None
    ) -> AsyncIterator[str]:
        """Generate a response with streaming"""
        model = model or self.model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"Ollama error: {str(e)}"

    async def chat(
        self,
        messages: list[dict],
        model: str = None,
        system: str = None
    ) -> str:
        """Chat completion (non-streaming)"""
        model = model or self.model

        # Add system message if provided
        if system:
            full_messages = [{"role": "system", "content": system}] + messages
        else:
            full_messages = messages

        payload = {
            "model": model,
            "messages": full_messages,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("message", {}).get("content", "")
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Ollama error: {str(e)}"


# Global instance
ollama_client = OllamaClient()
