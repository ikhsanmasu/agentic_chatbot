from openai import OpenAI
from llm.base import BaseLLM, LLMResponse


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", temperature: float = 0.7):
        super().__init__(model_name=model_name, temperature=temperature)
        self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, max_tokens: int = 150, system_prompt: str = None) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            generated_text=response.choices[0].message.content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        )

    def generate_chat(self, messages: list, max_tokens: int = 1024) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            generated_text=response.choices[0].message.content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        )
