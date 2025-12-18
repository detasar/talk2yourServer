"""
LLM Router

Handles routing between different LLM providers with fallback chain:
1. Ollama (on-prem) - if available and has GPU memory
2. Groq - cloud fallback with multiple models
3. OpenAI - final fallback
"""

import asyncio
from typing import AsyncIterator, Literal, Optional

from llm.ollama import ollama_client
from llm.groq_client import groq_client
from llm.openai_client import openai_client


Provider = Literal["ollama", "groq", "openai", "auto"]


class LLMRouter:
    """Routes requests to appropriate LLM provider"""

    def __init__(self):
        self.ollama = ollama_client
        self.groq = groq_client
        self.openai = openai_client

    def parse_suffix(self, text: str) -> tuple[str, Optional[str]]:
        """
        Parse message and extract provider suffix.
        Returns (clean_message, provider_or_none)

        Examples:
        "Hello ---openai" -> ("Hello", "openai")
        "What's the weather?" -> ("What's the weather?", None)
        """
        suffixes = {
            "---openai": "openai",
            "---groq": "groq",
            "---ollama": "ollama"
        }

        for suffix, provider in suffixes.items():
            if text.strip().endswith(suffix):
                clean = text.strip()[:-len(suffix)].strip()
                return clean, provider

        return text, None

    async def get_best_provider(self) -> tuple[str, str]:
        """
        Determine best available provider.
        Returns (provider_name, reason)
        """
        # Check Ollama first (on-prem)
        ollama_ok, ollama_reason = await self.ollama.is_available()
        if ollama_ok:
            return "ollama", "Using on-prem GPU"

        # Check Groq
        groq_ok, groq_reason = await self.groq.is_available()
        if groq_ok:
            return "groq", f"Groq Cloud (Ollama: {ollama_reason})"

        # Check OpenAI
        openai_ok, openai_reason = await self.openai.is_available()
        if openai_ok:
            return "openai", f"OpenAI (Ollama: {ollama_reason}, Groq: {groq_reason})"

        return "none", f"No provider available"

    async def chat(
        self,
        prompt: str,
        provider: Provider = "auto",
        system: str = None
    ) -> tuple[str, str]:
        """
        Chat with automatic provider selection.
        Returns (response, provider_used)
        """
        # Parse suffix from prompt
        clean_prompt, suffix_provider = self.parse_suffix(prompt)
        if suffix_provider:
            provider = suffix_provider
            prompt = clean_prompt

        # Auto-select provider
        if provider == "auto":
            provider, reason = await self.get_best_provider()
            if provider == "none":
                return f"No LLM provider available: {reason}", "none"

        messages = [{"role": "user", "content": prompt}]

        # Route to provider
        if provider == "ollama":
            response = await self.ollama.chat(messages, system=system)
            return response, "ollama"

        elif provider == "groq":
            response, model_used = await self.groq.chat(messages, system=system)
            return response, f"groq ({model_used})"

        elif provider == "openai":
            response = await self.openai.chat(messages, system=system)
            return response, "openai"

        return "Unknown provider", provider

    async def chat_stream(
        self,
        prompt: str,
        provider: Provider = "auto",
        system: str = None
    ) -> AsyncIterator[tuple[str, str]]:
        """
        Streaming chat with automatic provider selection.
        Yields (chunk, provider_used) tuples.
        First yield includes provider info.
        """
        # Parse suffix from prompt
        clean_prompt, suffix_provider = self.parse_suffix(prompt)
        if suffix_provider:
            provider = suffix_provider
            prompt = clean_prompt

        # Auto-select provider
        if provider == "auto":
            provider, reason = await self.get_best_provider()
            if provider == "none":
                yield f"No LLM provider available: {reason}", "none"
                return

        messages = [{"role": "user", "content": prompt}]

        # Route to provider
        if provider == "ollama":
            async for chunk in self.ollama.generate_stream(prompt, system=system):
                yield chunk, "ollama"

        elif provider == "groq":
            async for chunk in self.groq.chat_stream(messages, system=system):
                yield chunk, "groq"

        elif provider == "openai":
            async for chunk in self.openai.chat_stream(messages, system=system):
                yield chunk, "openai"

        else:
            yield "Unknown provider", provider

    async def get_provider_status(self) -> str:
        """Get status of all providers"""
        ollama_ok, ollama_msg = await self.ollama.is_available()
        groq_ok, groq_msg = await self.groq.is_available()
        openai_ok, openai_msg = await self.openai.is_available()

        best, reason = await self.get_best_provider()

        lines = [
            "LLM PROVIDER STATUS",
            "=" * 30,
            "",
            f"{'🟢' if ollama_ok else '🔴'} Ollama: {ollama_msg}",
            f"{'🟢' if groq_ok else '🔴'} Groq: {groq_msg}",
            f"{'🟢' if openai_ok else '🔴'} OpenAI: {openai_msg}",
            "",
            f"Active Provider: {best}",
            f"Reason: {reason}"
        ]

        return "\n".join(lines)


# Global instance
llm_router = LLMRouter()
