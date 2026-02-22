"""Quiz commands: list, view."""

import click

from ..context import pass_context
from ..output import output_table, output_detail, format_date, console


@click.group()
def quizzes():
    """Browse course quizzes."""
    pass


@quizzes.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_quizzes(ctx, course_id):
    """List quizzes in a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    data = api.get_quizzes(cid)

    rows = []
    for q in data:
        time_limit = q.get("time_limit")
        time_str = f"{time_limit}m" if time_limit else ""

        rows.append({
            "id": q["id"],
            "title": q.get("title", "Untitled"),
            "due": format_date(q.get("due_at")),
            "points": q.get("points_possible", ""),
            "questions": q.get("question_count", ""),
            "time": time_str,
        })

    output_table(rows, [
        ("ID", "id"),
        ("Title", "title"),
        ("Due", "due"),
        ("Points", "points"),
        ("Questions", "questions"),
        ("Time", "time"),
    ], ctx)


@quizzes.command()
@click.argument("quiz_id", type=int)
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def view(ctx, quiz_id, course_id):
    """View quiz details."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    q = api.get_quiz(cid, quiz_id)

    time_limit = q.get("time_limit")
    time_str = f"{time_limit} minutes" if time_limit else "No time limit"

    output_detail(q, [
        ("ID", "id"),
        ("Title", "title"),
        ("Due", "due_at"),
        ("Points", "points_possible"),
        ("Questions", "question_count"),
        ("Attempts", "allowed_attempts"),
        ("Published", "published"),
    ], ctx, title=q.get("title", "Quiz"))

    if not ctx.json_output:
        console.print(f"  [bold]Time Limit:[/bold] {time_str}")

        desc = q.get("description", "")
        if desc:
            console.print(f"\n[bold]Description:[/bold]")
            try:
                import html2text
                h = html2text.HTML2Text()
                h.body_width = 80
                console.print(h.handle(desc))
            except ImportError:
                console.print(desc)
