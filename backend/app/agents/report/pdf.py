from __future__ import annotations

import re

from fpdf import FPDF

_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?[-]+:?\s*(\|\s*:?[-]+:?\s*)+\|?$")
_MAX_TOKEN_LEN = 40


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


def _wrap_long_tokens(line: str, max_len: int = _MAX_TOKEN_LEN) -> str:
    if not line:
        return line
    words = line.split(" ")
    wrapped: list[str] = []
    for word in words:
        if len(word) <= max_len:
            wrapped.append(word)
            continue
        chunks = [word[i : i + max_len] for i in range(0, len(word), max_len)]
        wrapped.append(" ".join(chunks))
    return " ".join(wrapped)


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
            lines.append(_wrap_long_tokens(" | ".join(cells)))
            continue

        cleaned = _wrap_long_tokens(_strip_inline_markdown(raw))
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

    def _wrap_by_width(text: str, max_width: float) -> list[str]:
        if not text:
            return [""]
        words = text.split(" ")
        lines: list[str] = []
        current = ""

        for word in words:
            if word == "":
                continue
            candidate = word if not current else f"{current} {word}"
            if pdf.get_string_width(candidate) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            if pdf.get_string_width(word) <= max_width:
                current = word
                continue

            chunk = ""
            for ch in word:
                cand = chunk + ch
                if pdf.get_string_width(cand) <= max_width:
                    chunk = cand
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            current = chunk

        if current:
            lines.append(current)
        return lines

    pdf.set_font("Helvetica", "", 11)
    max_width = pdf.w - pdf.l_margin - pdf.r_margin
    for line in _markdown_to_lines(content):
        safe_line = _safe_text(line)
        if not safe_line.strip():
            pdf.ln(4)
            continue
        for wrapped_line in _wrap_by_width(safe_line, max_width):
            pdf.cell(0, 6, wrapped_line, ln=True)

    return pdf.output(dest="S").encode("latin-1")
