import json
import logging
import re
from collections.abc import Generator

from app.agents.base import AgentResult, BaseAgent
from app.agents.database.agent import DatabaseAgent
from app.agents.planner.prompts import (
    GENERAL_SYSTEM,
    ROUTING_SYSTEM,
    ROUTING_USER,
    SYNTHESIS_SYSTEM,
    SYNTHESIS_USER,
)
from app.agents.planner.schemas import PlannerDecision
from app.core.llm.base import BaseLLM
from app.core.llm.schemas import GenerateConfig

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, database_agent: DatabaseAgent):
        super().__init__(llm)
        self.database_agent = database_agent

    def _decide(self, message: str) -> PlannerDecision:
        messages = [
            {"role": "system", "content": ROUTING_SYSTEM},
            {"role": "user", "content": ROUTING_USER.format(message=message)},
        ]
        config = GenerateConfig(temperature=0)
        response = self.llm.generate(messages=messages, config=config)

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        try:
            parsed = json.loads(raw)
            return PlannerDecision(
                agent=parsed.get("agent", "general"),
                reasoning=parsed.get("reasoning", ""),
                rewritten_query=parsed.get("rewritten_query", message),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse routing decision, defaulting to general: %s", e)
            return PlannerDecision(
                agent="general",
                reasoning="Failed to parse routing decision, defaulting to general.",
                rewritten_query=message,
            )

    def execute(self, input_text: str, context: dict | None = None, history: list[dict] | None = None) -> AgentResult:
        decision = self._decide(input_text)

        if decision.agent == "database":
            db_result = self.database_agent.execute(decision.rewritten_query)

            # Synthesize the result into natural language
            messages = [
                {"role": "system", "content": SYNTHESIS_SYSTEM},
                {"role": "user", "content": SYNTHESIS_USER.format(
                    question=input_text,
                    results=db_result.output,
                )},
            ]
            response = self.llm.generate(messages=messages)
            return AgentResult(
                output=response.text,
                metadata={
                    "agent": "database",
                    "routing_reasoning": decision.reasoning,
                    **db_result.metadata,
                    "usage": response.usage,
                },
            )
        else:
            messages = [{"role": "system", "content": GENERAL_SYSTEM}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": input_text})
            response = self.llm.generate(messages=messages)
            return AgentResult(
                output=response.text,
                metadata={
                    "agent": "general",
                    "routing_reasoning": decision.reasoning,
                    "usage": response.usage,
                },
            )

    def execute_stream(self, input_text: str, context: dict | None = None, history: list[dict] | None = None) -> Generator[dict, None, None]:
        decision = self._decide(input_text)

        # Emit routing decision as thinking
        yield {
            "type": "thinking",
            "content": f"Routing to: {decision.agent}\nReasoning: {decision.reasoning}\n\n",
        }

        if decision.agent == "database":
            # Stream step-by-step thinking from DatabaseAgent
            db_result = None
            for event in self.database_agent.execute_stream(decision.rewritten_query):
                if event.get("type") == "_result":
                    db_result = event["data"]
                else:
                    yield event

            if db_result is None:
                yield {"type": "content", "content": "Error: Database agent returned no result."}
                return

            yield {"type": "thinking", "content": "Synthesizing response...\n"}

            # Stream synthesis
            messages = [
                {"role": "system", "content": SYNTHESIS_SYSTEM},
                {"role": "user", "content": SYNTHESIS_USER.format(
                    question=input_text,
                    results=db_result.output,
                )},
            ]
            chunks = self.llm.generate_stream(messages=messages)
            yield from _parse_think_tags(chunks)

        else:
            messages = [{"role": "system", "content": GENERAL_SYSTEM}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": input_text})
            chunks = self.llm.generate_stream(messages=messages)
            yield from _parse_think_tags(chunks)


def _parse_think_tags(chunks: Generator[str, None, None]) -> Generator[dict, None, None]:
    """Parse streamed chunks, separating <think>...</think> content from regular content."""
    buffer = ""
    in_think = False

    for chunk in chunks:
        buffer += chunk

        while True:
            if not in_think:
                idx = buffer.find("<think>")
                if idx == -1:
                    safe = buffer[:-7] if len(buffer) > 7 else ""
                    if safe:
                        yield {"type": "content", "content": safe}
                        buffer = buffer[len(safe):]
                    break
                else:
                    if idx > 0:
                        yield {"type": "content", "content": buffer[:idx]}
                    buffer = buffer[idx + 7:]
                    in_think = True
            else:
                idx = buffer.find("</think>")
                if idx == -1:
                    safe = buffer[:-8] if len(buffer) > 8 else ""
                    if safe:
                        yield {"type": "thinking", "content": safe}
                        buffer = buffer[len(safe):]
                    break
                else:
                    if idx > 0:
                        yield {"type": "thinking", "content": buffer[:idx]}
                    buffer = buffer[idx + 8:]
                    in_think = False

    if buffer:
        event_type = "thinking" if in_think else "content"
        yield {"type": event_type, "content": buffer}
