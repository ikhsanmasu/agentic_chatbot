import json
import logging
import re
from collections.abc import Generator
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.agents.database import DatabaseAgent
from app.core.llm.base import BaseLLM
from app.core.llm.schemas import GenerateConfig
from app.modules.admin.service import resolve_prompt

logger = logging.getLogger(__name__)

MAX_SECTIONS = 6
MAX_ROWS = 50


class ReportAgent(BaseAgent):
    def __init__(self, llm: BaseLLM, database_agent: DatabaseAgent):
        super().__init__(llm)
        self.database_agent = database_agent

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

    def _build_plan_messages(self, user_message: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("report_plan_system")},
            {"role": "user", "content": resolve_prompt("report_plan_user").format(message=user_message)},
        ]

    def _build_compile_messages(
        self, question: str, plan: dict[str, Any], sections: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": resolve_prompt("report_compile_system")},
            {
                "role": "user",
                "content": resolve_prompt("report_compile_user").format(
                    question=question,
                    plan=json.dumps(plan, ensure_ascii=True),
                    sections=json.dumps(sections, ensure_ascii=True),
                ),
            },
        ]

    def _parse_plan(self, raw_text: str) -> dict[str, Any] | None:
        raw = self._strip_json_fence(self._strip_think_tags(raw_text))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        sections = payload.get("sections")
        if not isinstance(sections, list) or not sections:
            return None
        payload["sections"] = sections[:MAX_SECTIONS]
        payload.setdefault("format", "markdown")
        payload.setdefault("title", "Laporan Operasional")
        payload.setdefault("period", "")
        return payload

    @staticmethod
    def _parse_table(output: str) -> tuple[list[str], list[list[str]]]:
        if "(no rows returned)" in output:
            return [], []
        parts = output.split("\n\n")
        if len(parts) < 2:
            return [], []
        table_block = parts[-1].strip()
        if not table_block or table_block.startswith("Error:"):
            return [], []
        lines = [line for line in table_block.splitlines() if line.strip()]
        if len(lines) < 2:
            return [], []
        columns = [c.strip() for c in lines[0].split(" | ")]
        rows: list[list[str]] = []
        for line in lines[2:]:
            row = [c.strip() for c in line.split(" | ")]
            if len(row) != len(columns):
                continue
            rows.append(row)
        return columns, rows

    @staticmethod
    def _table_to_markdown(columns: list[str], rows: list[list[str]]) -> str:
        if not columns:
            return "_(no data)_"
        header = "| " + " | ".join(columns) + " |"
        sep = "| " + " | ".join(["---"] * len(columns)) + " |"
        body_lines = []
        for row in rows[:MAX_ROWS]:
            body_lines.append("| " + " | ".join(row) + " |")
        return "\n".join([header, sep] + body_lines)

    def _fallback_report(self, plan: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
        title = plan.get("title") or "Laporan Operasional"
        period = plan.get("period") or ""
        lines = [f"# {title}"]
        if period:
            lines.append(f"_Periode: {period}_")
        lines.append("")
        for section in sections:
            lines.append(f"## {section.get('title', 'Bagian')}")
            if section.get("error"):
                lines.append(f"Catatan: {section.get('error')}")
                lines.append("")
                continue
            columns = section.get("columns") or []
            rows = section.get("rows") or []
            lines.append(self._table_to_markdown(columns, rows))
            lines.append("")
        content = "\n".join(lines).strip()
        filename = "report.md"
        return {
            "report": {
                "title": title,
                "period": period,
                "format": "markdown",
                "filename": filename,
                "content": content,
            }
        }

    @staticmethod
    def _attach_query(report_payload: dict[str, Any], question: str) -> dict[str, Any]:
        report = report_payload.get("report")
        if isinstance(report, dict):
            report.setdefault("query", question)
        return report_payload

    def _compile_report(self, question: str, plan: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
        messages = self._build_compile_messages(question, plan, sections)
        response = self.llm.generate(messages=messages, config=GenerateConfig(temperature=0.2))
        raw = self._strip_json_fence(self._strip_think_tags(response.text))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse report JSON, falling back.")
            return self._fallback_report(plan, sections)
        if not isinstance(payload, dict) or "report" not in payload:
            return self._fallback_report(plan, sections)
        return payload

    def execute(self, input_text: str, context: dict | None = None) -> AgentResult:
        question = input_text.strip()
        if not question:
            return AgentResult(output="Error: Empty query.", metadata={"error": "empty query"})

        plan_messages = self._build_plan_messages(question)
        plan_response = self.llm.generate(messages=plan_messages, config=GenerateConfig(temperature=0))
        plan = self._parse_plan(plan_response.text)
        if not plan:
            return AgentResult(output="Error: Failed to create report plan.", metadata={"error": "plan"})

        section_results: list[dict[str, Any]] = []
        for section in plan.get("sections", [])[:MAX_SECTIONS]:
            title = str(section.get("title") or "Bagian")
            instruction = str(section.get("instruction") or "").strip()
            if not instruction:
                section_results.append(
                    {"title": title, "error": "Instruksi kosong."}
                )
                continue

            db_result = self.database_agent.execute(instruction)
            if db_result.metadata.get("error") or str(db_result.output).startswith("Error:"):
                section_results.append(
                    {
                        "title": title,
                        "instruction": instruction,
                        "error": str(db_result.output),
                    }
                )
                continue

            columns, rows = self._parse_table(db_result.output)
            section_results.append(
                {
                    "title": title,
                    "instruction": instruction,
                    "columns": columns,
                    "rows": rows[:MAX_ROWS],
                    "row_count": len(rows),
                }
            )

        report_payload = self._attach_query(
            self._compile_report(question, plan, section_results), question
        )
        return AgentResult(
            output=json.dumps(report_payload, ensure_ascii=True),
            metadata={
                "plan": plan,
                "sections": section_results,
            },
        )

    def execute_stream(self, input_text: str, context: dict | None = None) -> Generator[dict, None, None]:
        question = input_text.strip()
        if not question:
            yield {"type": "content", "content": "Error: Empty query."}
            return

        yield {"type": "thinking", "content": "Menyusun rencana laporan...\n"}
        plan_messages = self._build_plan_messages(question)
        plan_response = self.llm.generate(messages=plan_messages, config=GenerateConfig(temperature=0))
        plan = self._parse_plan(plan_response.text)
        if not plan:
            yield {"type": "content", "content": "Error: Failed to create report plan."}
            return

        section_results: list[dict[str, Any]] = []
        for idx, section in enumerate(plan.get("sections", [])[:MAX_SECTIONS], start=1):
            title = str(section.get("title") or f"Bagian {idx}")
            instruction = str(section.get("instruction") or "").strip()
            yield {"type": "thinking", "content": f"Mengambil data: {title}\n"}

            if not instruction:
                section_results.append({"title": title, "error": "Instruksi kosong."})
                continue

            db_result = self.database_agent.execute(instruction)
            if db_result.metadata.get("error") or str(db_result.output).startswith("Error:"):
                section_results.append(
                    {
                        "title": title,
                        "instruction": instruction,
                        "error": str(db_result.output),
                    }
                )
                continue

            columns, rows = self._parse_table(db_result.output)
            section_results.append(
                {
                    "title": title,
                    "instruction": instruction,
                    "columns": columns,
                    "rows": rows[:MAX_ROWS],
                    "row_count": len(rows),
                }
            )

        yield {"type": "thinking", "content": "Menyusun dokumen laporan...\n"}
        report_payload = self._attach_query(
            self._compile_report(question, plan, section_results), question
        )
        result = AgentResult(
            output=json.dumps(report_payload, ensure_ascii=True),
            metadata={
                "plan": plan,
                "sections": section_results,
            },
        )
        yield {"type": "_result", "data": result}
