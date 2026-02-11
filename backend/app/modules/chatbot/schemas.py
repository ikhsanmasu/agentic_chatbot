from typing import Optional

from pydantic import BaseModel


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []


class ChatResponse(BaseModel):
    status: str
    response: str
    usage: dict


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    status: str
    response: str
    sql: str
    row_count: int


# ── Conversation schemas ──

class MessageSchema(BaseModel):
    role: str
    content: str
    thinking: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: float
    updated_at: float


class ConversationDetail(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: float
    updated_at: float
    messages: list[MessageSchema]


class CreateConversationRequest(BaseModel):
    title: str = "New Chat"


class UpdateConversationTitleRequest(BaseModel):
    title: str


class SaveMessagesRequest(BaseModel):
    user_message: str
    assistant_content: str
    assistant_thinking: Optional[str] = None
