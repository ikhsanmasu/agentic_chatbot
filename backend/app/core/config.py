from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Chatbot
    CHATBOT_DEFAULT_LLM: str = "openai"
    CHATBOT_LLM_API_KEYS: str = ""
    CHATBOT_DEFAULT_MODEL: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
