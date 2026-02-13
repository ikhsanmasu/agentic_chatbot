from __future__ import annotations

import re

from fpdf import FPDF

_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?[-]+:?\s*(\|\s*:?[-]+:?\s*)+\|?$")


def _safe_text(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


def _strip_inline_markdown(line: str) -> str:
    line = re.sub(r"^#{1,6}\s+", "", line)
    line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    line = re.sub(r"\*(.*?)\*", r"\1", line)
    line = re.sub(r"_(.*?)_", r"\1", line)
    line = re.sub(r"`(.*?)`", r"\1", line)
    line = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", line)
    return line


def _markdown_to_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    in_code = False

    for raw in markdown.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue

        if in_code:
            lines.append(raw)
            continue

        if stripped.startswith("|") and "|" in stripped:
            if _TABLE_SEPARATOR_RE.match(stripped):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            lines.append(" | ".join(cells))
            continue

        cleaned = _strip_inline_markdown(raw)
        lines.append(cleaned)

    return lines


def build_report_pdf(report: dict) -> bytes:
    title = str(report.get("title") or "Report")
    period = str(report.get("period") or "")
    content = str(report.get("content") or "")

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _safe_text(title), ln=True)

    if period:
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, _safe_text(f"Periode: {period}"), ln=True)
        pdf.ln(1)

    pdf.set_font("Helvetica", "", 11)
    for line in _markdown_to_lines(content):
        safe_line = _safe_text(line)
        if not safe_line.strip():
            pdf.ln(4)
            continue
        pdf.multi_cell(0, 6, safe_line)

    return pdf.output(dest="S").encode("latin-1")
