"""Announcement commands: list, view."""

import click

from ..context import pass_context
from ..output import output_table, format_date, console, truncate


@click.group()
def announcements():
    """Browse course announcements."""
    pass


@announcements.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_announcements(ctx, course_id):
    """List announcements for a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    data = api.get_announcements(cid)

    rows = []
    for a in data:
        rows.append({
            "id": a["id"],
            "title": truncate(a.get("title", "Untitled"), 50),
            "posted": format_date(a.get("posted_at")),
            "author": a.get("author", {}).get("display_name", ""),
        })

    output_table(rows, [
        ("ID", "id"),
        ("Title", "title"),
        ("Posted", "posted"),
        ("Author", "author"),
    ], ctx)


@announcements.command()
@click.argument("announcement_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def view(ctx, announcement_id, course_id):
    """View an announcement."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    # Announcements are discussion topics
    a = api.get_discussion(cid, announcement_id)

    if ctx.json_output:
        import json
        click.echo(json.dumps(a, indent=2, default=str))
        return

    console.print(f"\n[bold]{a.get('title', 'Untitled')}[/bold]")
    console.print(f"[dim]Posted: {format_date(a.get('posted_at'))}[/dim]")
    author = a.get("author", {}).get("display_name", "")
    if author:
        console.print(f"[dim]By: {author}[/dim]")
    console.print()

    message = a.get("message", "")
    if message:
        try:
            import html2text
            h = html2text.HTML2Text()
            h.body_width = 80
            console.print(h.handle(message))
        except ImportError:
            console.print(message)
    else:
        console.print("[dim]No content.[/dim]")
