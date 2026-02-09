from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from chat.service import chat
import time


chatbot_router = APIRouter(tags=["Chatbot"], prefix="/v1/chatbot")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


@chatbot_router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Kirim pesan ke chatbot dan dapatkan respons.

    - **message**: Pesan dari user
    - **history**: Opsional, riwayat percakapan sebelumnya
    """
    start_time = time.time()

    try:
        history = None
        if request.history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.history]

        result = chat(message=request.message, history=history)

        processing_time = round(time.time() - start_time, 4)

        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "response": result["response"],
                    "usage": result["usage"],
                },
                "processing_time": f"{processing_time}s"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat: {str(e)}"
        )
