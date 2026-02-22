"""Root CLI group for canvascli."""

import click
import rich_click

from .context import CanvasContext

# Configure rich-click for nice help output
rich_click.rich_click.USE_RICH_MARKUP = True
rich_click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
rich_click.rich_click.SHOW_ARGUMENTS = True


@click.group()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON instead of tables.")
@click.option("--course", "course_id", type=int, default=None, help="Course ID (can be set per-command too).")
@click.version_option(package_name="canvascli")
@click.pass_context
def cli(ctx, json_output, course_id):
    """Canvas CLI - interact with Canvas LMS from the terminal."""
    ctx.ensure_object(CanvasContext)
    ctx.obj.json_output = json_output
    ctx.obj.course_id = course_id


def register_commands():
    """Register all command groups (called after cli is defined to avoid circular imports)."""
    from .commands import auth, courses, modules, assignments, files, pages, grades
    from .commands import announcements, discussions, quizzes, todo, calendar, pull

    cli.add_command(auth.auth)
    cli.add_command(courses.courses)
    cli.add_command(modules.modules)
    cli.add_command(assignments.assignments)
    cli.add_command(files.files)
    cli.add_command(pages.pages)
    cli.add_command(grades.grades)
    cli.add_command(announcements.announcements)
    cli.add_command(discussions.discussions)
    cli.add_command(quizzes.quizzes)
    cli.add_command(todo.todo)
    cli.add_command(calendar.calendar_cmd, name="calendar")
    cli.add_command(pull.pull)


register_commands()
