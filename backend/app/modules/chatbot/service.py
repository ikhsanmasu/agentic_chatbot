import json
from collections.abc import Generator

from app.core.llm import create_llm
from app.modules.chatbot.schemas import ChatRequest, ChatResponse

SYSTEM_PROMPT = (
    "Kamu adalah asisten AI yang membantu dan ramah. "
    "Sebelum menjawab, pikirkan langkah-langkahmu di dalam tag <think>...</think>, "
    "lalu berikan jawaban final di luar tag tersebut."
)


def _build_messages(user_message: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def chat(request: ChatRequest) -> ChatResponse:
    llm = create_llm()

    response = llm.generate(messages=_build_messages(request.message))

    return ChatResponse(
        status="success",
        response=response.text,
        usage=response.usage,
    )


def _parse_think_tags(chunks: Generator[str, None, None]) -> Generator[dict, None, None]:
    """Parse streamed chunks, separating <think>...</think> content from regular content."""
    buffer = ""
    in_think = False

    for chunk in chunks:
        buffer += chunk

        while True:
            if not in_think:
                idx = buffer.find("<think>")
                if idx == -1:
                    # Keep tail in case of partial "<think" tag
                    safe = buffer[:-7] if len(buffer) > 7 else ""
                    if safe:
                        yield {"type": "content", "content": safe}
                        buffer = buffer[len(safe):]
                    break
                else:
                    if idx > 0:
                        yield {"type": "content", "content": buffer[:idx]}
                    buffer = buffer[idx + 7:]
                    in_think = True
            else:
                idx = buffer.find("</think>")
                if idx == -1:
                    safe = buffer[:-8] if len(buffer) > 8 else ""
                    if safe:
                        yield {"type": "thinking", "content": safe}
                        buffer = buffer[len(safe):]
                    break
                else:
                    if idx > 0:
                        yield {"type": "thinking", "content": buffer[:idx]}
                    buffer = buffer[idx + 8:]
                    in_think = False

    # flush remaining buffer
    if buffer:
        event_type = "thinking" if in_think else "content"
        yield {"type": event_type, "content": buffer}


def chat_stream(request: ChatRequest) -> Generator[str, None, None]:
    llm = create_llm()
    chunks = llm.generate_stream(messages=_build_messages(request.message))

    for event in _parse_think_tags(chunks):
        yield f"data: {json.dumps(event)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
