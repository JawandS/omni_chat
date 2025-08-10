import httpx
from typing import List, Dict
from flask import current_app
from .base import ChatProvider


class GeminiProvider(ChatProvider):
    name = 'gemini'
    display_name = 'Google Gemini'

    async def chat(self, messages: List[Dict[str, str]], model: str, api_key: str) -> str:
        base = current_app.config.get('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com')
        url = f"{base}/v1beta/models/{model}:generateContent?key={api_key}"
        # Convert to Gemini contents
        contents = []
        for m in messages:
            role = 'user' if m['role'] == 'user' else 'model'
            contents.append({'role': role, 'parts': [{'text': m['content']}]})
        payload = {
            'contents': contents
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            # Extract text
            cands = data.get('candidates', [])
            if not cands:
                return ''
            parts = cands[0].get('content', {}).get('parts', [])
            out = []
            for p in parts:
                if 'text' in p:
                    out.append(p['text'])
            return '\n'.join(out)
