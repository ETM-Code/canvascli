"""Grades command: list."""

import click

from ..context import pass_context
from ..output import output_table, console


@click.group()
def grades():
    """View grades and submissions."""
    pass


@grades.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_grades(ctx, course_id):
    """View your grades for a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    # Show enrollment-level grade summary
    enrollments = api.get_enrollments(cid)
    for enrollment in enrollments:
        grade_info = enrollment.get("grades", {})
        if grade_info:
            console.print(f"\n[bold]Course Grade:[/bold]")
            current = grade_info.get("current_grade") or grade_info.get("current_score")
            final = grade_info.get("final_grade") or grade_info.get("final_score")
            if current:
                console.print(f"  Current: {current}")
            if final:
                console.print(f"  Final:   {final}")
            console.print()

    # Show per-assignment grades
    try:
        submissions = api.get_submissions(cid)
    except Exception:
        console.print("[yellow]Could not fetch individual submissions.[/yellow]")
        return

    rows = []
    for s in submissions:
        assignment = s.get("assignment", {}) or {}
        score = s.get("score")
        points = assignment.get("points_possible")

        score_str = ""
        if score is not None and points:
            score_str = f"{score}/{points}"
        elif score is not None:
            score_str = str(score)

        rows.append({
            "name": assignment.get("name", "Unknown"),
            "score": score_str,
            "grade": s.get("grade", ""),
            "state": s.get("workflow_state", ""),
        })

    output_table(rows, [
        ("Assignment", "name"),
        ("Score", "score"),
        ("Grade", "grade"),
        ("Status", "state"),
    ], ctx)
