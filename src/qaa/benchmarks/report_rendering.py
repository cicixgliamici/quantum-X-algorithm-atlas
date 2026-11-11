"""Render one semantic scientific document as Markdown and standalone HTML."""

import base64
from html import escape
from pathlib import Path

from qaa.benchmarks.report_sections import Section, Table

TITLE = "Monte Carlo and Iterative Amplitude Estimation"
SUBTITLE = "Quantum Algorithm Atlas · Reproducible calibration and resource study"
STYLES = """
:root { color-scheme: light; }
body { margin: 0; background: #f4f6f8; color: #182432; font: 16px/1.65 Georgia, serif; }
main { max-width: 1120px; margin: 32px auto; padding: 48px; background: white; }
header { border-bottom: 3px solid #245a81; padding-bottom: 26px; }
h1,h2,thead { font-family: system-ui, sans-serif; }
h1 { font-size: 32px; line-height: 1.2; margin-bottom: 14px; }
h2 { font-size: 23px; margin-top: 42px; color: #245a81; }
header p { font-family: system-ui, sans-serif; color: #526170; margin: 0; }
p { overflow-wrap: anywhere; }
.table-wrap { overflow-x: auto; margin: 24px 0; }
table { border-collapse: collapse; width: 100%; font: 12px/1.5 system-ui, sans-serif; }
th,td { border-bottom: 1px solid #dce2e8; padding: 9px 10px; text-align: left; }
th { background: #eef3f7; font-weight: 650; }
tbody tr:nth-child(even) { background: #f8fafb; }
td { font-variant-numeric: tabular-nums; }
figure { margin: 28px 0; break-inside: avoid; }
figure img { width: 100%; height: auto; display: block; }
figcaption { color: #526170; font: 13px/1.6 system-ui, sans-serif; margin-top: 12px; }
a { color: #245a81; }
@media (max-width: 700px) { main { margin: 0; padding: 24px; } h1 { font-size: 27px; } }
@media print { body { background: white; } main { margin: 0; padding: 0; }
  h2 { break-after: avoid; } table { font-size: 9px; } th,td { padding: 5px; }
  thead { display: table-header-group; } .table-wrap { overflow: visible; } }
"""


def html_cell(value: str) -> str:
    """Only complete HTTPS reference cells become links; every value is escaped."""
    if value.startswith("https://"):
        return f'<a href="{escape(value, quote=True)}">{escape(value)}</a>'
    return escape(value)


def html_table(table: Table) -> str:
    """Use real header cells for accessible tables, including wide resource ledgers."""
    headers = "".join(f'<th scope="col">{escape(value)}</th>' for value in table.headers)
    rows = "".join(
        "<tr>" + "".join(f"<td>{html_cell(value)}</td>" for value in row) + "</tr>"
        for row in table.rows
    )
    return (
        f'<div class="table-wrap"><table><thead><tr>{headers}</tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def markdown_cell(value: str) -> str:
    """Protect table separators while retaining readable plain numerical text."""
    if value.startswith("https://"):
        return f"[source]({value})"
    return value.replace("|", "\\|").replace("\n", " ")


def markdown_table(table: Table) -> str:
    """The HTML and Markdown tables consume exactly the same formatted cells."""
    rows = [table.headers, tuple("---" for _ in table.headers), *table.rows]
    return "\n".join(
        "| " + " | ".join(markdown_cell(value) for value in row) + " |" for row in rows
    )


def render_html(sections: list[Section], output: Path) -> str:
    """Embed PNG bytes so the HTML can be copied without its figure directory."""
    blocks = [f"<header><h1>{escape(TITLE)}</h1><p>{escape(SUBTITLE)}</p></header>"]
    for index, section in enumerate(sections, start=1):
        blocks.append(f'<section id="section-{index}"><h2>{index}. {escape(section.title)}</h2>')
        blocks.extend(f"<p>{escape(paragraph)}</p>" for paragraph in section.paragraphs)
        blocks.extend(html_table(table) for table in section.tables)
        if section.figure:
            encoded = base64.b64encode(
                (output / "figures" / f"{section.figure}.png").read_bytes()
            ).decode("ascii")
            blocks.append(
                f'<figure><img src="data:image/png;base64,{encoded}" alt="{escape(section.title)}">'
                f"<figcaption>{escape(section.caption)}</figcaption></figure>"
            )
        blocks.append("</section>")
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(TITLE)}</title><style>{STYLES}</style></head>"
        "<body><main>" + "\n".join(blocks) + "</main></body></html>\n"
    )


def render_markdown(sections: list[Section]) -> str:
    """Keep figure links relative for portable review of the complete report folder."""
    blocks = [f"# {TITLE}", SUBTITLE]
    for index, section in enumerate(sections, start=1):
        blocks.append(f"## {index}. {section.title}")
        blocks.extend(section.paragraphs)
        blocks.extend(markdown_table(table) for table in section.tables)
        if section.figure:
            blocks.extend([f"![{section.title}](figures/{section.figure}.png)", section.caption])
    return "\n\n".join(blocks) + "\n"
