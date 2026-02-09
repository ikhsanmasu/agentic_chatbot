from fastapi import FastAPI
from controller import chatbot_router

app = FastAPI(title="Agentic Chatbot API")

app.include_router(chatbot_router)
