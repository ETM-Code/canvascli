"""Shared CLI context for canvascli commands."""

import click


class CanvasContext:
    """Shared context passed to all commands."""

    def __init__(self):
        self.json_output: bool = False
        self.course_id: int | None = None
        self.api = None

    def require_auth(self):
        """Ensure the user is authenticated. Exits if not."""
        from canvas_api import get_canvas_client
        self.api = get_canvas_client()
        if not self.api:
            click.echo("Not authenticated. Run 'canvascli auth login' first.")
            raise SystemExit(1)
        return self.api

    def require_course(self) -> int:
        """Get the course ID, prompting if not set."""
        if self.course_id:
            return self.course_id
        click.echo("Error: --course is required. Specify a course ID.")
        click.echo("Run 'canvascli courses list' to see available courses.")
        raise SystemExit(1)


pass_context = click.make_pass_decorator(CanvasContext, ensure=True)
