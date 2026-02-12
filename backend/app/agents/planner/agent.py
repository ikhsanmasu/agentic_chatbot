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

    def _build_db_plan_messages(self, user_message: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("db_plan_system")},
            {"role": "user", "content": resolve_prompt("db_plan_user").format(question=user_message)},
        ]

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

    def _build_db_reflection_messages(
        self,
        question: str,
        plan: str,
        instruction: str,
        error: str,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("db_reflection_system")},
            {
                "role": "user",
                "content": resolve_prompt("db_reflection_user").format(
                    question=question,
                    plan=plan or "-",
                    instruction=instruction,
                    error=error,
                ),
            },
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

    def _parse_json(self, raw_text: str) -> dict | None:
        raw = self._strip_json_fence(raw_text)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    @staticmethod
    def _format_plan_summary(plan: dict | None) -> str:
        if not plan:
            return ""
        parts: list[str] = []
        steps = plan.get("steps") if isinstance(plan.get("steps"), list) else None
        tables = plan.get("tables") if isinstance(plan.get("tables"), list) else None
        filters = plan.get("filters") if isinstance(plan.get("filters"), list) else None
        time_range = plan.get("time_range")
        risk = plan.get("risk")
        notes = plan.get("notes")

        if steps:
            parts.append("Langkah: " + "; ".join(str(s) for s in steps))
        if tables:
            parts.append("Tabel: " + ", ".join(str(t) for t in tables))
        if filters:
            parts.append("Filter: " + "; ".join(str(f) for f in filters))
        if time_range:
            parts.append(f"Rentang waktu: {time_range}")
        if risk:
            parts.append(f"Risiko: {risk}")
        if notes:
            parts.append(f"Catatan: {notes}")
        return "\n".join(parts)

    @staticmethod
    def _should_reflect(db_result: AgentResult) -> bool:
        if db_result.metadata.get("error"):
            return True
        output = db_result.output or ""
        return isinstance(output, str) and output.strip().startswith("Error:")

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
            plan_summary = ""
            plan_usage = None
            try:
                plan_messages = self._build_db_plan_messages(decision.routed_input)
                plan_config = GenerateConfig(temperature=0)
                plan_response = self.llm.generate(messages=plan_messages, config=plan_config)
                plan_usage = plan_response.usage
                plan_payload = self._parse_json(plan_response.text)
                plan_summary = self._format_plan_summary(plan_payload)
                if not plan_summary:
                    plan_summary = self._strip_think_tags(plan_response.text)
            except Exception as exc:
                logger.warning("Failed to build plan: %s", exc)

            command_input = decision.routed_input
            if plan_summary:
                command_input = f"{decision.routed_input}\n\nRencana:\n{plan_summary}"
            command_messages = self._build_db_command_messages(command_input)
            command_config = GenerateConfig(temperature=0)
            command_response = self.llm.generate(messages=command_messages, config=command_config)
            db_instruction = self._strip_think_tags(command_response.text)

            db_result = self.database_agent.execute(db_instruction)

            reflection_usage = None
            if self._should_reflect(db_result):
                error_msg = db_result.metadata.get("error") or db_result.output
                reflection_messages = self._build_db_reflection_messages(
                    question=input_text,
                    plan=plan_summary,
                    instruction=db_instruction,
                    error=str(error_msg),
                )
                reflection_config = GenerateConfig(temperature=0)
                reflection_response = self.llm.generate(
                    messages=reflection_messages,
                    config=reflection_config,
                )
                reflection_usage = reflection_response.usage
                reflected_instruction = self._strip_think_tags(reflection_response.text)
                if reflected_instruction and reflected_instruction != db_instruction:
                    db_instruction = reflected_instruction
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
                    "plan": plan_summary,
                    "plan_usage": plan_usage,
                    "db_instruction": db_instruction,
                    "instruction_usage": command_response.usage,
                    "reflection_usage": reflection_usage,
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
            plan_summary = ""
            yield {"type": "thinking", "content": "Menyusun rencana query...\n"}
            try:
                plan_messages = self._build_db_plan_messages(decision.routed_input)
                plan_config = GenerateConfig(temperature=0)
                plan_response = self.llm.generate(messages=plan_messages, config=plan_config)
                plan_payload = self._parse_json(plan_response.text)
                plan_summary = self._format_plan_summary(plan_payload)
                if not plan_summary:
                    plan_summary = self._strip_think_tags(plan_response.text)
            except Exception as exc:
                logger.warning("Failed to build plan: %s", exc)

            if plan_summary:
                yield {
                    "type": "thinking",
                    "content": f"Rencana query\n{plan_summary}\n\n",
                }

            command_input = decision.routed_input
            if plan_summary:
                command_input = f"{decision.routed_input}\n\nRencana:\n{plan_summary}"
            command_messages = self._build_db_command_messages(command_input)
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

            if self._should_reflect(db_result):
                error_msg = db_result.metadata.get("error") or db_result.output
                yield {"type": "thinking", "content": "Refleksi selektif: memperbaiki instruksi...\n"}
                reflection_messages = self._build_db_reflection_messages(
                    question=input_text,
                    plan=plan_summary,
                    instruction=db_instruction,
                    error=str(error_msg),
                )
                reflection_config = GenerateConfig(temperature=0)
                reflection_response = self.llm.generate(
                    messages=reflection_messages,
                    config=reflection_config,
                )
                reflected_instruction = self._strip_think_tags(reflection_response.text)
                if reflected_instruction and reflected_instruction != db_instruction:
                    db_instruction = reflected_instruction
                    yield {
                        "type": "thinking",
                        "content": f"Instruksi hasil refleksi: {db_instruction}\n\n",
                    }

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
