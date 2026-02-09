from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 150

@dataclass(frozen=True)
class LLMResponse:
    generated_text: str
    usage: Optional[Dict[str, Any]] = None

class BaseLLM:
    """Base class for Language Model implementations."""

    def __init__(self, model_name: str, temperature: float = 0.7):
        self.model_name = model_name
        self.temperature = temperature

    def generate(self, prompt: str, max_tokens: int = 150) -> str:
        """Generate text based on the given prompt.

        Args:
            prompt (str): The input prompt to generate text from.
            max_tokens (int): The maximum number of tokens to generate.

        Returns:
            str: The generated text.
        """
        raise NotImplementedError("This method should be overridden by subclasses.")
