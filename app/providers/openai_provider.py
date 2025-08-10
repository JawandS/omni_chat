import httpx
from typing import List, Dict
from flask import current_app
from .base import ChatProvider


class OpenAIProvider(ChatProvider):
    name = 'openai'
    display_name = 'OpenAI'

    async def chat(self, messages: List[Dict[str, str]], model: str, api_key: str) -> str:
        base = current_app.config.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
        url = f"{base}/chat/completions"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': model,
            'messages': messages,
            'temperature': 0.7,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data['choices'][0]['message']['content']
