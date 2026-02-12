from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.agents.database.router import router as database_router
from app.core.database import close_app_database, init_app_database
from app.core.logging import setup_logging
from app.middleware.cors import setup_cors
from app.modules.admin.router import router as admin_router
from app.modules.chatbot.router import router as chatbot_router

setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_app_database()
    try:
        yield
    finally:
        close_app_database()


app = FastAPI(title="M Agent API", lifespan=lifespan)

setup_cors(app)

app.include_router(chatbot_router)
app.include_router(database_router)
app.include_router(admin_router)
