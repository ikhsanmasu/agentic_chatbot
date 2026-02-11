from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Chatbot
    CHATBOT_DEFAULT_LLM: str = "openai"
    CHATBOT_LLM_API_KEYS: str = ""
    CHATBOT_DEFAULT_MODEL: str = "gpt-4o-mini"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ClickHouse
    CLICKHOUSE_HOST: str = "192.168.100.19"
    CLICKHOUSE_PORT: int = 8722
    CLICKHOUSE_USER: str = "admin"
    CLICKHOUSE_PASSWORD: str = "adminadmin123"
    CLICKHOUSE_DB: str = "default"

    @property
    def database_url(self) -> str:
        return (
            f"clickhousedb://{self.CLICKHOUSE_USER}:{self.CLICKHOUSE_PASSWORD}"
            f"@{self.CLICKHOUSE_HOST}:{self.CLICKHOUSE_PORT}/{self.CLICKHOUSE_DB}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
