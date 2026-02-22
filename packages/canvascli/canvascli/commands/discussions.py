"""Discussion commands: list, view, reply."""

import click

from ..context import pass_context
from ..output import output_table, format_date, console, truncate
from ..confirm import confirm_action


@click.group()
def discussions():
    """Browse and participate in discussions."""
    pass


@discussions.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_discussions(ctx, course_id):
    """List discussion topics in a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    data = api.get_discussions(cid)

    rows = []
    for d in data:
        rows.append({
            "id": d["id"],
            "title": truncate(d.get("title", "Untitled"), 50),
            "posted": format_date(d.get("posted_at")),
            "replies": d.get("discussion_subentry_count", 0),
            "unread": d.get("unread_count", 0),
        })

    output_table(rows, [
        ("ID", "id"),
        ("Title", "title"),
        ("Posted", "posted"),
        ("Replies", "replies"),
        ("Unread", "unread"),
    ], ctx)


@discussions.command()
@click.argument("discussion_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def view(ctx, discussion_id, course_id):
    """View a discussion and its replies."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    topic = api.get_discussion(cid, discussion_id)

    if ctx.json_output:
        import json
        # Include entries in JSON output
        entries = api.get_discussion_entries(cid, discussion_id)
        topic["entries"] = entries
        click.echo(json.dumps(topic, indent=2, default=str))
        return

    console.print(f"\n[bold]{topic.get('title', 'Untitled')}[/bold]")
    console.print(f"[dim]Posted: {format_date(topic.get('posted_at'))}[/dim]")
    author = topic.get("author", {}).get("display_name", "")
    if author:
        console.print(f"[dim]By: {author}[/dim]")
    console.print()

    message = topic.get("message", "")
    if message:
        try:
            import html2text
            h = html2text.HTML2Text()
            h.body_width = 80
            console.print(h.handle(message))
        except ImportError:
            console.print(message)

    # Show replies
    try:
        entries = api.get_discussion_entries(cid, discussion_id)
        if entries:
            console.print(f"\n[bold]Replies ({len(entries)}):[/bold]\n")
            for entry in entries:
                author_name = entry.get("user_name", "Unknown")
                date = format_date(entry.get("created_at"))
                console.print(f"  [cyan]{author_name}[/cyan] [dim]({date})[/dim]")
                entry_msg = entry.get("message", "")
                if entry_msg:
                    try:
                        import html2text
                        h = html2text.HTML2Text()
                        h.body_width = 76
                        text = h.handle(entry_msg).strip()
                        for line in text.split("\n"):
                            console.print(f"    {line}")
                    except ImportError:
                        console.print(f"    {entry_msg}")
                console.print()
    except Exception:
        pass


@discussions.command()
@click.argument("discussion_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@click.option("--message", "-m", required=True, help="Reply message text.")
@pass_context
def reply(ctx, discussion_id, course_id, message):
    """Reply to a discussion topic."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    topic = api.get_discussion(cid, discussion_id)

    if not confirm_action(
        f"Post reply to '{topic.get('title', discussion_id)}'",
        details={
            "Course": str(cid),
            "Discussion": topic.get("title", str(discussion_id)),
            "Message": message[:100] + ("..." if len(message) > 100 else ""),
        },
    ):
        console.print("[dim]Cancelled.[/dim]")
        return

    try:
        api.create_discussion_entry(cid, discussion_id, message)
        console.print("[green]Reply posted![/green]")
    except Exception as e:
        console.print(f"[red]Failed to post reply: {e}[/red]")
