"""
Groq Client

Handles communication with Groq Cloud API.
Uses fallback chain through multiple models.

Based on Groq documentation:
- AsyncGroq for async operations
- chat.completions.create() for chat
- Streaming with stream=True
- max_completion_tokens parameter
"""

import asyncio
from typing import AsyncIterator, Optional

from groq import AsyncGroq, RateLimitError, APIError

from config import config


class GroqClient:
    """Client for Groq Cloud API with model fallback"""

    def __init__(self, api_key: str = None, models: list[str] = None):
        self.api_key = api_key or config.groq_api_key
        self.models = models or config.groq_models
        self.client = None

    def _get_client(self) -> AsyncGroq:
        """Get or create async client"""
        if self.client is None:
            self.client = AsyncGroq(api_key=self.api_key)
        return self.client

    async def is_available(self) -> tuple[bool, str]:
        """Check if Groq API is available"""
        if not self.api_key:
            return False, "GROQ_API_KEY not configured"

        try:
            client = self._get_client()
            # Try a minimal request to check availability
            response = await client.chat.completions.create(
                model=self.models[0],
                messages=[{"role": "user", "content": "test"}],
                max_completion_tokens=5
            )
            return True, "Groq ready"
        except RateLimitError:
            return False, "Groq rate limit exceeded"
        except Exception as e:
            return False, f"Groq error: {str(e)}"

    async def chat(
        self,
        messages: list[dict],
        model: str = None,
        system: str = None,
        max_tokens: int = 4096
    ) -> tuple[str, str]:
        """
        Chat completion with model fallback.
        Returns (response_text, model_used)

        Rate limits (Developer/Free plan):
        - Most models: 250K-300K TPM, 1K RPM
        - Compound systems: 200K TPM, 200 RPM
        """
        if not self.api_key:
            return "GROQ_API_KEY not configured", ""

        client = self._get_client()

        # Prepare messages with system prompt
        if system:
            full_messages = [{"role": "system", "content": system}] + messages
        else:
            full_messages = messages

        # If specific model requested, try only that
        models_to_try = [model] if model else self.models

        last_error = ""
        for try_model in models_to_try:
            try:
                response = await client.chat.completions.create(
                    model=try_model,
                    messages=full_messages,
                    max_completion_tokens=max_tokens,
                    temperature=0.7,
                    top_p=1,
                    stream=False
                )
                content = response.choices[0].message.content
                return content, try_model

            except RateLimitError as e:
                last_error = f"Rate limit ({try_model})"
                continue

            except APIError as e:
                error_str = str(e).lower()
                if "model" in error_str and ("not found" in error_str or "unavailable" in error_str):
                    last_error = f"Model not available: {try_model}"
                    continue
                last_error = str(e)
                continue

            except Exception as e:
                last_error = str(e)
                continue

        return f"All Groq models failed: {last_error}", ""

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = None,
        system: str = None,
        max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        """
        Streaming chat completion.
        Falls back to non-streaming on error.
        """
        if not self.api_key:
            yield "GROQ_API_KEY not configured"
            return

        client = self._get_client()

        # Prepare messages
        if system:
            full_messages = [{"role": "system", "content": system}] + messages
        else:
            full_messages = messages

        # Try first 3 models for streaming
        models_to_try = [model] if model else self.models[:3]

        for try_model in models_to_try:
            try:
                stream = await client.chat.completions.create(
                    model=try_model,
                    messages=full_messages,
                    max_completion_tokens=max_tokens,
                    temperature=0.7,
                    top_p=1,
                    stream=True
                )

                # Iterate through stream chunks
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return

            except Exception as e:
                continue

        # All models failed, try non-streaming
        response, _ = await self.chat(messages, system=system, max_tokens=max_tokens)
        yield response

    async def simple_prompt(
        self,
        prompt: str,
        system: str = None,
        model: str = None
    ) -> str:
        """Simple prompt interface"""
        messages = [{"role": "user", "content": prompt}]
        response, _ = await self.chat(messages, model=model, system=system)
        return response


# Global instance
groq_client = GroqClient()
