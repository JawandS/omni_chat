from typing import Dict
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider


PROVIDERS: Dict[str, object] = {
    'openai': OpenAIProvider(),
    'anthropic': AnthropicProvider(),
    'gemini': GeminiProvider(),
}
