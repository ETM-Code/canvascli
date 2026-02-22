"""Todo command."""

import click

from ..context import pass_context
from ..output import output_table, format_date, truncate


@click.command()
@pass_context
def todo(ctx):
    """View your Canvas to-do items."""
    api = ctx.require_auth()

    data = api.get_todo_items()

    if not data:
        click.echo("No to-do items.")
        return

    rows = []
    for item in data:
        assignment = item.get("assignment", {}) or {}
        course_name = item.get("context_name", "")

        rows.append({
            "type": item.get("type", ""),
            "title": truncate(assignment.get("name", item.get("type", "?")), 50),
            "course": truncate(course_name, 30),
            "due": format_date(assignment.get("due_at")),
        })

    output_table(rows, [
        ("Type", "type"),
        ("Title", "title"),
        ("Course", "course"),
        ("Due", "due"),
    ], ctx)
