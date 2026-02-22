"""Calendar command."""

import click

from ..context import pass_context
from ..output import output_table, format_date, truncate, console


@click.command("calendar")
@click.option("--days", default=14, help="Number of days ahead to show (default: 14).")
@pass_context
def calendar_cmd(ctx, days):
    """View upcoming calendar events and due dates."""
    api = ctx.require_auth()

    # Fetch both events and assignments
    events = api.get_calendar_events(days=days)
    assignments = api.get_calendar_assignments(days=days)

    all_items = []

    for e in events:
        all_items.append({
            "type": "Event",
            "title": truncate(e.get("title", "Untitled"), 50),
            "date": format_date(e.get("start_at")),
            "context": e.get("context_name", ""),
        })

    for a in assignments:
        assignment = a.get("assignment", {}) or {}
        all_items.append({
            "type": "Assignment",
            "title": truncate(a.get("title", assignment.get("name", "Untitled")), 50),
            "date": format_date(a.get("start_at") or assignment.get("due_at")),
            "context": a.get("context_name", ""),
        })

    if not all_items:
        console.print(f"[dim]No events in the next {days} days.[/dim]")
        return

    # Sort by date
    all_items.sort(key=lambda x: x["date"])

    output_table(all_items, [
        ("Type", "type"),
        ("Title", "title"),
        ("Date", "date"),
        ("Course", "context"),
    ], ctx, title=f"Next {days} Days")
