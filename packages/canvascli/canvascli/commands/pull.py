"""Pull command - wraps canvas-course-puller for bulk downloads."""

from pathlib import Path

import click

from ..context import pass_context
from ..output import console


@click.command()
@click.option("--course", "course_id", type=int, default=None, help="Course ID.")
@click.option("--output", "-o", "output_dir", type=click.Path(), default=None, help="Output directory.")
@click.option("--no-pdf", is_flag=True, help="Skip PDF conversion.")
@click.option("--no-combine", is_flag=True, help="Skip PDF combining.")
@pass_context
def pull(ctx, course_id, output_dir, no_pdf, no_combine):
    """Bulk download a course (modules, files, pages, etc).

    This wraps the canvas-course-puller functionality for
    non-interactive bulk downloading of entire courses.
    """
    api = ctx.require_auth()
    cid = course_id or ctx.require_course()

    # Get course info
    course = api.get_course(cid)
    course_name = course.get("name", "course")

    from canvas_course_puller.downloader import CourseDownloader, sanitize_filename
    safe_name = sanitize_filename(course_name)

    # Determine output directory
    if output_dir:
        base_dir = Path(output_dir)
    else:
        base_dir = Path.cwd() / "canvas_download"

    course_dir = base_dir / safe_name
    course_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Downloading: {course_name}[/bold]")
    console.print(f"[dim]Output: {course_dir}[/dim]\n")

    # Step 1: Download
    downloader = CourseDownloader(api, cid, course_dir)
    items = downloader.download_all()

    if not items:
        console.print("[yellow]No content was downloaded.[/yellow]")
        return

    console.print(f"\n[green]Downloaded {len(items)} items[/green]")

    if no_pdf:
        console.print(f"\n[green]Done! Files saved to {course_dir}[/green]")
        return

    # Step 2: Convert to PDF
    from canvas_course_puller.pdf_converter import PDFConverter
    console.print("\n[bold cyan]Converting to PDF...[/bold cyan]")
    converter = PDFConverter(course_dir)
    converted_pdfs = converter.convert_all(items)

    if not converted_pdfs or no_combine:
        console.print(f"\n[green]Done! Files saved to {course_dir}[/green]")
        return

    # Step 3: Combine PDFs
    from canvas_course_puller.pdf_combiner import PDFCombiner
    console.print("\n[bold cyan]Combining PDFs...[/bold cyan]")
    combiner = PDFCombiner(course_dir)
    combined = combiner.combine(converted_pdfs, f"{safe_name}_complete.pdf")

    if combined:
        console.print(f"\n[green]Done! Combined PDF: {combined}[/green]")
    else:
        console.print(f"\n[green]Done! Files saved to {course_dir}[/green]")
