"""File commands: list, download, upload."""

from pathlib import Path

import click

from ..context import pass_context
from ..output import output_table, console
from ..confirm import confirm_action


@click.group()
def files():
    """Browse and manage course files."""
    pass


@files.command("list")
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@pass_context
def list_files(ctx, course_id):
    """List files in a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    try:
        data = api.get_files(cid)
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            console.print("[yellow]Course files not accessible (restricted by instructor).[/yellow]")
            return
        raise

    rows = []
    for f in data:
        size = f.get("size", 0)
        if size > 1_000_000:
            size_str = f"{size / 1_000_000:.1f} MB"
        elif size > 1_000:
            size_str = f"{size / 1_000:.1f} KB"
        else:
            size_str = f"{size} B"

        rows.append({
            "id": f["id"],
            "name": f.get("display_name", f.get("filename", "?")),
            "size": size_str,
            "updated": f.get("updated_at", "")[:10] if f.get("updated_at") else "",
        })

    output_table(rows, [
        ("ID", "id"),
        ("Name", "name"),
        ("Size", "size"),
        ("Updated", "updated"),
    ], ctx)


@files.command()
@click.argument("file_id", type=int)
@click.option("--output", "-o", "output_path", type=click.Path(), default=None, help="Save to this path.")
@pass_context
def download(ctx, file_id, output_path):
    """Download a file by ID."""
    api = ctx.require_auth()

    file_info = api.get_file(file_id)
    file_url = file_info.get("url")
    filename = file_info.get("filename", file_info.get("display_name", f"file_{file_id}"))

    if not file_url:
        console.print("[red]No download URL available for this file.[/red]")
        return

    dest = Path(output_path) if output_path else Path.cwd() / filename
    console.print(f"[dim]Downloading {filename}...[/dim]")
    api.download_file(file_url, dest)
    console.print(f"[green]Saved to {dest}[/green]")


@files.command()
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="File to upload.")
@click.option("--folder", "folder_path", default="/", help="Destination folder in course files.")
@pass_context
def upload(ctx, course_id, file_path, folder_path):
    """Upload a file to a course."""
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()
    fp = Path(file_path)

    if not confirm_action(
        f"Upload '{fp.name}' to course {cid}",
        details={
            "File": str(fp),
            "Size": f"{fp.stat().st_size / 1024:.1f} KB",
            "Destination": folder_path,
        },
    ):
        console.print("[dim]Cancelled.[/dim]")
        return

    console.print("[dim]Uploading...[/dim]")
    try:
        result = api.upload_file(cid, fp, folder_path)
        console.print(f"[green]Uploaded {fp.name} successfully![/green]")
    except Exception as e:
        console.print(f"[red]Upload failed: {e}[/red]")
