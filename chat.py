from dataclasses import dataclass


@dataclass
class ChatReply:
    reply: str


def generate_reply(provider: str, model: str, message: str) -> ChatReply:
    """Placeholder chat generation logic.

    Right now, we simply echo the message, prefixed with provider/model.
    Replace this with real LLM calls later.
    """
    reply = f"[{provider}/{model}] Echo: {message}"
    return ChatReply(reply=reply)
