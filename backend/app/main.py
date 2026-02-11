from fastapi import FastAPI

from app.core.logging import setup_logging
from app.middleware.cors import setup_cors
from app.modules.chatbot.router import router as chatbot_router

setup_logging()

app = FastAPI(title="Agentic Chatbot API")

setup_cors(app)

app.include_router(chatbot_router)
