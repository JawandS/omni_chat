import httpx
from typing import List, Dict
from flask import current_app
from .base import ChatProvider


class AnthropicProvider(ChatProvider):
    name = 'anthropic'
    display_name = 'Anthropic'

    async def chat(self, messages: List[Dict[str, str]], model: str, api_key: str) -> str:
        base = current_app.config.get('ANTHROPIC_API_BASE', 'https://api.anthropic.com')
        url = f"{base}/v1/messages"
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        # Convert OpenAI-style messages to Anthropic format
        converted = []
        for m in messages:
            role = 'user' if m['role'] == 'user' else 'assistant'
            if m['role'] == 'system':
                # prepend as user message
                converted.append({'role': 'user', 'content': m['content']})
            else:
                converted.append({'role': role, 'content': m['content']})
        payload = {
            'model': model,
            'max_tokens': 1024,
            'messages': converted,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            # Anthropic responses: {'content': [{'text': '...', 'type': 'text'}], ...}
            parts = data.get('content', [])
            for p in parts:
                if p.get('type') == 'text':
                    return p.get('text', '')
            return ''
