"""Output formatting helpers for table/JSON switching."""

import json

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def output_table(data: list[dict], columns: list[tuple[str, str]], ctx_obj, title: str | None = None):
    """Output data as a rich table or JSON.

    Args:
        data: List of dicts to display.
        columns: List of (header, key) tuples.
        ctx_obj: CanvasContext with json_output flag.
        title: Optional table title.
    """
    if ctx_obj.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if not data:
        console.print("[dim]No results.[/dim]")
        return

    table = Table(title=title, show_lines=False)
    for header, _ in columns:
        table.add_column(header)

    for row in data:
        values = []
        for _, key in columns:
            val = row.get(key, "")
            if val is None:
                val = ""
            values.append(str(val))
        table.add_row(*values)

    console.print(table)


def output_detail(data: dict, fields: list[tuple[str, str]], ctx_obj, title: str | None = None):
    """Output a single item's details as key-value pairs or JSON.

    Args:
        data: Dict to display.
        fields: List of (label, key) tuples.
        ctx_obj: CanvasContext with json_output flag.
        title: Optional panel title.
    """
    if ctx_obj.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    lines = []
    for label, key in fields:
        val = data.get(key, "")
        if val is None:
            val = ""
        lines.append(f"[bold]{label}:[/bold] {val}")

    content = "\n".join(lines)
    if title:
        console.print(Panel(content, title=title, border_style="blue"))
    else:
        console.print(content)


def output_json(data, ctx_obj):
    """Output raw data as JSON (for complex or unstructured data)."""
    click.echo(json.dumps(data, indent=2, default=str))


def format_date(date_str: str | None) -> str:
    """Format an ISO date string for display."""
    if not date_str:
        return "N/A"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %I:%M %p")
    except (ValueError, AttributeError):
        return date_str


def truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
