"""Course commands: list, view."""

import click

from ..context import pass_context
from ..output import output_table, output_detail, format_date


@click.group()
def courses():
    """Browse your Canvas courses."""
    pass


@courses.command("list")
@click.option("--favorites", is_flag=True, help="Show only favorite courses.")
@pass_context
def list_courses(ctx, favorites):
    """List your courses."""
    api = ctx.require_auth()

    if favorites:
        data = api.get_favorite_courses()
    else:
        data = api.get_courses(include_favorites=True)

    # Sort: favorites first, then alphabetical
    data.sort(key=lambda c: (not c.get("is_favorite", False), c.get("name", "").lower()))

    rows = []
    for c in data:
        rows.append({
            "id": c["id"],
            "name": c.get("name", "Untitled"),
            "code": c.get("course_code", ""),
            "fav": "*" if c.get("is_favorite") else "",
            "term": c.get("enrollment_term_id", ""),
        })

    output_table(rows, [
        ("ID", "id"),
        ("Name", "name"),
        ("Code", "code"),
        ("Fav", "fav"),
    ], ctx)


@courses.command()
@click.argument("course_id", type=int)
@pass_context
def view(ctx, course_id):
    """View details for a course."""
    api = ctx.require_auth()
    course = api.get_course(course_id)

    output_detail(course, [
        ("ID", "id"),
        ("Name", "name"),
        ("Code", "course_code"),
        ("Start", "start_at"),
        ("End", "end_at"),
        ("Students", "total_students"),
        ("Workflow", "workflow_state"),
    ], ctx, title=course.get("name", "Course"))
