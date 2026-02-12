import json
import logging
import re
from collections.abc import Generator

from app.agents.base import AgentResult, BaseAgent
from app.agents.database.agent import DatabaseAgent
from app.agents.planner.schemas import DATABASE_ROUTE, GENERAL_ROUTE, RoutingDecision
from app.agents.planner.streaming import parse_think_tags
from app.core.llm.base import BaseLLM
from app.core.llm.schemas import GenerateConfig
from app.modules.admin.service import resolve_prompt

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, database_agent: DatabaseAgent):
        super().__init__(llm)
        self.database_agent = database_agent

    def _build_routing_messages(self, user_message: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("routing_system")},
            {"role": "user", "content": resolve_prompt("routing_user").format(message=user_message)},
        ]

    def _build_general_messages(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": resolve_prompt("general_system")},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_synthesis_messages(self, question: str, database_output: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("synthesis_system")},
            {"role": "user", "content": resolve_prompt("synthesis_user").format(
                question=question,
                results=database_output,
            )},
        ]

    def _build_db_command_messages(self, user_message: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("db_command_system")},
            {"role": "user", "content": resolve_prompt("db_command_user").format(message=user_message)},
        ]

    @staticmethod
    def _strip_json_fence(raw_text: str) -> str:
        raw = raw_text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        return raw

    @staticmethod
    def _strip_think_tags(raw_text: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
        return cleaned.strip()

    def _route_message(self, user_message: str) -> RoutingDecision:
        messages = self._build_routing_messages(user_message)
        config = GenerateConfig(temperature=0)
        response = self.llm.generate(messages=messages, config=config)

        raw = self._strip_json_fence(response.text)

        try:
            parsed = json.loads(raw)
            return RoutingDecision.from_payload(parsed, fallback_input=user_message)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse route decision, defaulting to general: %s", e)
            return RoutingDecision(
                target_agent=GENERAL_ROUTE,
                reasoning="Failed to parse routing decision, defaulting to general.",
                routed_input=user_message,
            )

    def execute(self, input_text: str, context: dict | None = None, history: list[dict] | None = None) -> AgentResult:
        decision = self._route_message(input_text)

        if decision.target_agent == DATABASE_ROUTE:
            command_messages = self._build_db_command_messages(decision.routed_input)
            command_config = GenerateConfig(temperature=0)
            command_response = self.llm.generate(messages=command_messages, config=command_config)
            db_instruction = self._strip_think_tags(command_response.text)

            db_result = self.database_agent.execute(db_instruction)

            # Synthesize the result into natural language
            messages = self._build_synthesis_messages(
                question=input_text,
                database_output=db_result.output,
            )
            response = self.llm.generate(messages=messages)
            return AgentResult(
                output=response.text,
                metadata={
                    "agent": decision.target_agent,
                    "routing_reasoning": decision.reasoning,
                    "db_instruction": db_instruction,
                    "instruction_usage": command_response.usage,
                    **db_result.metadata,
                    "usage": response.usage,
                },
            )

        messages = self._build_general_messages(input_text, history=history)
        response = self.llm.generate(messages=messages)
        return AgentResult(
            output=response.text,
            metadata={
                "agent": decision.target_agent,
                "routing_reasoning": decision.reasoning,
                "usage": response.usage,
            },
        )

    def execute_stream(self, input_text: str, context: dict | None = None, history: list[dict] | None = None) -> Generator[dict, None, None]:
        decision = self._route_message(input_text)

        # Emit routing decision as thinking
        yield {
            "type": "thinking",
            "content": (
                "Routing permintaan\n"
                f"Target: {decision.target_agent}\n"
                f"Alasan: {decision.reasoning}\n\n"
            ),
        }

        if decision.target_agent == DATABASE_ROUTE:
            command_messages = self._build_db_command_messages(decision.routed_input)
            command_config = GenerateConfig(temperature=0)
            command_response = self.llm.generate(messages=command_messages, config=command_config)
            db_instruction = self._strip_think_tags(command_response.text)

            yield {
                "type": "thinking",
                "content": (
                    "Instruksi ke Database Agent\n"
                    f"Instruksi: {db_instruction}\n\n"
                ),
            }

            # Stream step-by-step thinking from DatabaseAgent
            db_result = None
            for event in self.database_agent.execute_stream(db_instruction):
                if event.get("type") == "_result":
                    db_result = event["data"]
                else:
                    yield event

            if db_result is None:
                yield {"type": "content", "content": "Error: Database agent returned no result."}
                return

            yield {"type": "thinking", "content": "Menyusun jawaban akhir...\n"}

            # Stream synthesis
            messages = self._build_synthesis_messages(
                question=input_text,
                database_output=db_result.output,
            )
            chunks = self.llm.generate_stream(messages=messages)
            yield from parse_think_tags(chunks)

            return

        messages = self._build_general_messages(input_text, history=history)
        chunks = self.llm.generate_stream(messages=messages)
        yield from parse_think_tags(chunks)
