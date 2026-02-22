"""Assignment commands: list, view, submit."""

from pathlib import Path

import click

from ..context import pass_context
from ..output import output_table, output_detail, format_date, console
from ..confirm import confirm_action


@click.group()
def assignments():
    """Browse and submit assignments."""
    pass


@assignments.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_assignments(ctx, course_id):
    """List assignments in a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    data = api.get_assignments(cid)

    rows = []
    for a in data:
        submission = a.get("submission", {}) or {}
        rows.append({
            "id": a["id"],
            "name": a.get("name", "Untitled"),
            "due": format_date(a.get("due_at")),
            "points": a.get("points_possible", ""),
            "status": submission.get("workflow_state", ""),
        })

    output_table(rows, [
        ("ID", "id"),
        ("Name", "name"),
        ("Due", "due"),
        ("Points", "points"),
        ("Status", "status"),
    ], ctx)


@assignments.command()
@click.argument("assignment_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def view(ctx, assignment_id, course_id):
    """View assignment details."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    a = api.get_assignment(cid, assignment_id)

    output_detail(a, [
        ("ID", "id"),
        ("Name", "name"),
        ("Due", "due_at"),
        ("Points", "points_possible"),
        ("Submission Types", "submission_types"),
        ("Published", "published"),
    ], ctx, title=a.get("name", "Assignment"))

    # Show description as rendered text
    if not ctx.json_output and a.get("description"):
        try:
            import html2text
            h = html2text.HTML2Text()
            h.body_width = 80
            console.print("\n[bold]Description:[/bold]")
            console.print(h.handle(a["description"]))
        except ImportError:
            pass


@assignments.command()
@click.argument("assignment_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="File to submit.")
@pass_context
def submit(ctx, assignment_id, course_id, file_path):
    """Submit a file to an assignment."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()
    fp = Path(file_path)

    # Get assignment info for confirmation
    a = api.get_assignment(cid, assignment_id)

    if not confirm_action(
        f"Submit '{fp.name}' to assignment '{a.get('name', assignment_id)}'",
        details={
            "Course": str(cid),
            "Assignment": a.get("name", str(assignment_id)),
            "File": str(fp),
            "Size": f"{fp.stat().st_size / 1024:.1f} KB",
        },
    ):
        console.print("[dim]Cancelled.[/dim]")
        return

    console.print("[dim]Uploading...[/dim]")
    try:
        result = api.submit_assignment(cid, assignment_id, fp)
        console.print(f"[green]Submitted successfully![/green]")
    except Exception as e:
        console.print(f"[red]Submission failed: {e}[/red]")
