"""Module commands: list, view."""

import click

from ..context import pass_context
from ..output import output_table, truncate


@click.group()
def modules():
    """Browse course modules."""
    pass


@modules.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_modules(ctx, course_id):
    """List modules in a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    data = api.get_modules(cid, include_items=False)

    rows = []
    for m in data:
        rows.append({
            "id": m["id"],
            "name": m.get("name", "Untitled"),
            "state": m.get("state", ""),
            "items": m.get("items_count", ""),
        })

    output_table(rows, [
        ("ID", "id"),
        ("Name", "name"),
        ("State", "state"),
        ("Items", "items"),
    ], ctx)


@modules.command()
@click.argument("module_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def view(ctx, module_id, course_id):
    """View items in a module."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    items = api.get_module_items(cid, module_id)

    rows = []
    for item in items:
        rows.append({
            "id": item.get("id", ""),
            "title": truncate(item.get("title", "Untitled"), 50),
            "type": item.get("type", ""),
            "content_id": item.get("content_id", ""),
        })

    output_table(rows, [
        ("ID", "id"),
        ("Title", "title"),
        ("Type", "type"),
        ("Content ID", "content_id"),
    ], ctx)
