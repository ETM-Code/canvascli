"""Pages commands: list, view."""

import click

from ..context import pass_context
from ..output import output_table, output_detail, format_date, console, truncate


@click.group()
def pages():
    """Browse course wiki pages."""
    pass


@pages.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_pages(ctx, course_id):
    """List wiki pages in a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    data = api.get_pages(cid)

    rows = []
    for p in data:
        rows.append({
            "url": p.get("url", ""),
            "title": truncate(p.get("title", "Untitled"), 60),
            "updated": format_date(p.get("updated_at")),
            "published": "yes" if p.get("published") else "no",
        })

    output_table(rows, [
        ("Slug", "url"),
        ("Title", "title"),
        ("Updated", "updated"),
        ("Published", "published"),
    ], ctx)


@pages.command()
@click.argument("page_slug")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def view(ctx, page_slug, course_id):
    """View a wiki page. Use the slug from 'pages list'."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    page = api.get_page(cid, page_slug)

    if ctx.json_output:
        import json
        click.echo(json.dumps(page, indent=2, default=str))
        return

    console.print(f"\n[bold]{page.get('title', 'Untitled')}[/bold]")
    console.print(f"[dim]Updated: {format_date(page.get('updated_at'))}[/dim]\n")

    body = page.get("body", "")
    if body:
        try:
            import html2text
            h = html2text.HTML2Text()
            h.body_width = 80
            console.print(h.handle(body))
        except ImportError:
            console.print(body)
    else:
        console.print("[dim]No content.[/dim]")
