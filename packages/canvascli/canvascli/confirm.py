"""Confirmation helpers for mutating actions."""

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def confirm_action(action: str, details: dict | None = None) -> bool:
    """Require explicit confirmation before a mutating action.

    Args:
        action: Description of what will happen.
        details: Optional key-value details to display.

    Returns:
        True if user confirmed, False otherwise.
    """
    lines = [f"[bold yellow]{action}[/bold yellow]"]
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"  [bold]{key}:[/bold] {value}")

    console.print(Panel(
        "\n".join(lines),
        title="Confirmation Required",
        border_style="yellow",
    ))

    return click.confirm("Proceed?", default=False)
