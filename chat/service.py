import os
from dotenv import load_dotenv
from llm.implementation.openai import OpenAILLM

load_dotenv()

OPENAI_API_KEY = os.getenv("CHATBOT_LLM_API_KEYS", "")
DEFAULT_MODEL = os.getenv("CHATBOT_DEFAULT_MODEL", "gpt-4o-mini")

# Singleton LLM instance
_llm_instance = None


def get_llm() -> OpenAILLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = OpenAILLM(api_key=OPENAI_API_KEY, model_name=DEFAULT_MODEL)
    return _llm_instance


SYSTEM_PROMPT = "Kamu adalah asisten AI Maxmar yang membantu dan ramah. Jawab pertanyaan dengan jelas dan ringkas dalam bahasa yang sama dengan pengguna."


def chat(message: str, history: list = None) -> dict:
    llm = get_llm()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    response = llm.generate_chat(messages=messages, max_tokens=1024)

    return {
        "response": response.generated_text,
        "usage": response.usage,
    }
