"""
OpenAI Client

Handles communication with OpenAI API.
Used as final fallback in the LLM chain.
"""

import asyncio
from typing import AsyncIterator, Optional

from openai import AsyncOpenAI, RateLimitError, APIError

from config import config


class OpenAIClient:
    """Client for OpenAI API"""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or config.openai_api_key
        self.model = model or config.openai_model
        self.client = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create async client"""
        if self.client is None:
            self.client = AsyncOpenAI(api_key=self.api_key)
        return self.client

    async def is_available(self) -> tuple[bool, str]:
        """Check if OpenAI API is available"""
        if not self.api_key:
            return False, "OPENAI_API_KEY not configured"

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True, "OpenAI ready"
        except RateLimitError:
            return False, "OpenAI rate limit exceeded"
        except Exception as e:
            return False, f"OpenAI error: {str(e)}"

    async def chat(
        self,
        messages: list[dict],
        model: str = None,
        system: str = None,
        max_tokens: int = 4096
    ) -> str:
        """Chat completion"""
        if not self.api_key:
            return "OPENAI_API_KEY not configured"

        client = self._get_client()
        model = model or self.model

        # Prepare messages
        if system:
            full_messages = [{"role": "system", "content": system}] + messages
        else:
            full_messages = messages

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content

        except RateLimitError:
            return "OpenAI rate limit exceeded. Please wait a moment."
        except APIError as e:
            return f"OpenAI API error: {str(e)}"
        except Exception as e:
            return f"OpenAI error: {str(e)}"

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = None,
        system: str = None,
        max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        """Streaming chat completion"""
        if not self.api_key:
            yield "OPENAI_API_KEY not configured"
            return

        client = self._get_client()
        model = model or self.model

        # Prepare messages
        if system:
            full_messages = [{"role": "system", "content": system}] + messages
        else:
            full_messages = messages

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"OpenAI error: {str(e)}"

    async def simple_prompt(
        self,
        prompt: str,
        system: str = None,
        model: str = None
    ) -> str:
        """Simple prompt interface"""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model=model, system=system)


# Global instance
openai_client = OpenAIClient()
