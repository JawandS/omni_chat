from abc import ABC, abstractmethod
from typing import List, Dict


class ChatProvider(ABC):
    name: str
    display_name: str

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], model: str, api_key: str) -> str:
        ...
