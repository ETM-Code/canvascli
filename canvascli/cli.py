"""Main CLI entry point for Canvas CLI."""

import subprocess
import sys
import webbrowser
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .canvas_api import CanvasAPI, get_canvas_client, load_config, save_config
from .downloader import CourseDownloader, sanitize_filename
from .pdf_converter import PDFConverter
from .pdf_combiner import PDFCombiner


console = Console()


def print_banner():
    """Print the application banner."""
    banner = """
╔═══════════════════════════════════════════╗
║           Canvas Course Downloader        ║
║     Download & Convert Course Content     ║
╚═══════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


def configure_canvas() -> CanvasAPI | None:
    """Configure Canvas API credentials with browser-assisted token generation."""
    console.print("\n[bold yellow]Canvas Configuration[/bold yellow]\n")

    # Step 1: Get Canvas URL
    canvas_url = questionary.text(
        "Enter your Canvas URL (e.g., https://canvas.university.edu):",
        validate=lambda x: len(x) > 0 and x.startswith("http"),
    ).ask()

    if not canvas_url:
        return None

    canvas_url = canvas_url.rstrip("/")

    # Step 2: Open browser to token generation page
    token_url = f"{canvas_url}/profile/settings"

    console.print(Panel(
        "[bold]Opening your browser to Canvas settings...[/bold]\n\n"
        "1. Log in to Canvas if prompted\n"
        "2. Scroll down to [cyan]'Approved Integrations'[/cyan]\n"
        "3. Click [cyan]'+ New Access Token'[/cyan]\n"
        "4. Enter a purpose (e.g., 'Canvas CLI')\n"
        "5. Click [cyan]'Generate Token'[/cyan]\n"
        "6. [bold yellow]Copy the token[/bold yellow] (you won't see it again!)",
        title="Generate Access Token",
        border_style="blue",
    ))

    # Open browser
    open_browser = questionary.confirm(
        "Open browser to Canvas settings?",
        default=True,
    ).ask()

    if open_browser:
        webbrowser.open(token_url)
        console.print(f"\n[dim]Opened: {token_url}[/dim]\n")

    # Step 3: Get the token
    console.print("[bold]Paste your access token below:[/bold]")
    access_token = questionary.password(
        "Access Token:",
        validate=lambda x: len(x) > 10,
    ).ask()

    if not access_token:
        return None

    # Test the connection
    console.print("\n[dim]Testing connection...[/dim]")
    try:
        api = CanvasAPI(canvas_url, access_token)
        courses = api.get_courses()
        console.print(f"[green]Connected! Found {len(courses)} courses.[/green]")

        # Ask to save configuration
        save_creds = questionary.confirm(
            "Save credentials for future use?",
            default=True,
        ).ask()

        if save_creds:
            save_config({
                "CANVAS_URL": canvas_url,
                "CANVAS_TOKEN": access_token,
            })
            console.print("[green]Configuration saved to ~/.config/canvascli/config[/green]")

        return api

    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        retry = questionary.confirm("Try again?", default=True).ask()
        if retry:
            return configure_canvas()
        return None


def select_course(api: CanvasAPI) -> dict | None:
    """Show course selection menu with favorites first."""
    console.print("\n[bold]Fetching your courses...[/bold]")

    try:
        all_courses = api.get_courses(include_favorites=True)
    except Exception as e:
        console.print(f"[red]Failed to fetch courses: {e}[/red]")
        return None

    if not all_courses:
        console.print("[yellow]No courses found.[/yellow]")
        return None

    # Separate favorites from other courses
    favorites = [c for c in all_courses if c.get("is_favorite")]
    other_courses = [c for c in all_courses if not c.get("is_favorite")]

    def make_choice(course: dict) -> questionary.Choice:
        name = course.get("name", "Untitled Course")
        code = course.get("course_code", "")
        label = f"{name} ({code})" if code else name
        return questionary.Choice(title=label, value=course)

    # Build choices list
    choices = []

    if favorites:
        choices.append(questionary.Separator("── Favorites ──"))
        for course in favorites:
            choices.append(make_choice(course))

    if other_courses:
        choices.append(questionary.Separator())
        choices.append(questionary.Choice(
            title=f"Other Courses ({len(other_courses)})...",
            value="__show_other__"
        ))

    choices.append(questionary.Separator())
    choices.append(questionary.Choice(title="← Exit", value=None))

    # Show selection menu
    console.print("\n[bold blue]Select a course:[/bold blue]\n")
    selected = questionary.select(
        "Choose a course to download:",
        choices=choices,
        use_shortcuts=True,
    ).ask()

    # Handle "Other Courses" submenu
    if selected == "__show_other__":
        other_choices = [make_choice(c) for c in other_courses]
        other_choices.append(questionary.Separator())
        other_choices.append(questionary.Choice(title="← Back", value="__back__"))

        console.print("\n[bold blue]Other Courses:[/bold blue]\n")
        selected = questionary.select(
            "Choose a course:",
            choices=other_choices,
            use_shortcuts=True,
        ).ask()

        if selected == "__back__":
            return select_course(api)  # Go back to main menu

    return selected


def select_output_directory() -> Path | None:
    """Ask user for output directory using native folder picker."""
    default_dir = Path.cwd() / "canvas_download"

    choice = questionary.select(
        "Where to save downloaded content?",
        choices=[
            questionary.Choice(f"Default ({default_dir})", value="default"),
            questionary.Choice("Choose folder...", value="choose"),
        ],
    ).ask()

    if choice == "default":
        return default_dir

    if choice == "choose":
        # Use native macOS folder picker via osascript
        try:
            result = subprocess.run(
                [
                    "osascript", "-e",
                    'set theFolder to choose folder with prompt "Select output folder for Canvas download"',
                    "-e", 'POSIX path of theFolder',
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
            else:
                console.print("[yellow]No folder selected[/yellow]")
                return None
        except Exception as e:
            console.print(f"[red]Could not open folder picker: {e}[/red]")
            # Fallback to text input
            custom_path = questionary.path(
                "Enter output directory:",
                only_directories=True,
            ).ask()
            if custom_path:
                return Path(custom_path)

    return None


def show_summary(course: dict, output_dir: Path, downloaded_count: int, pdf_count: int, combined_path: Path | None):
    """Show download summary."""
    table = Table(title="Download Summary", show_header=False)
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Course", course.get("name", "Unknown"))
    table.add_row("Output Directory", str(output_dir))
    table.add_row("Items Downloaded", str(downloaded_count))
    table.add_row("PDFs Created", str(pdf_count))
    if combined_path:
        table.add_row("Combined PDF", combined_path.name)

    console.print()
    console.print(table)


def run_download(api: CanvasAPI, course: dict, output_dir: Path):
    """Run the download and conversion process."""
    course_id = course["id"]
    course_name = course.get("name", "course")
    safe_name = sanitize_filename(course_name)

    # Create course-specific output directory
    course_dir = output_dir / safe_name
    course_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold]Downloading: {course_name}[/bold]\n"
        f"Output: {course_dir}",
        title="Starting Download",
        border_style="blue",
    ))

    # Step 1: Download all content
    console.print("\n[bold cyan]Step 1/3: Downloading content[/bold cyan]")
    downloader = CourseDownloader(api, course_id, course_dir)
    items = downloader.download_all()

    if not items:
        console.print("[yellow]No content was downloaded.[/yellow]")
        return

    console.print(f"\n[green]Downloaded {len(items)} items[/green]")

    # Step 2: Convert to PDF
    console.print("\n[bold cyan]Step 2/3: Converting to PDF[/bold cyan]")
    converter = PDFConverter(course_dir)
    converted_pdfs = converter.convert_all(items)

    if not converted_pdfs:
        console.print("[yellow]No PDFs were created.[/yellow]")
        return

    # Step 3: Combine PDFs
    console.print("\n[bold cyan]Step 3/3: Combining PDFs[/bold cyan]")
    combiner = PDFCombiner(course_dir)
    combined_path = combiner.combine(converted_pdfs, f"{safe_name}_complete.pdf")

    # Show summary
    show_summary(course, course_dir, len(items), len(converted_pdfs), combined_path)

    # Ask about cleanup
    console.print()
    remove_intermediate = questionary.confirm(
        "Remove intermediate PDF files? (keeps only the combined PDF)",
        default=False,
    ).ask()

    if remove_intermediate:
        combiner.cleanup_intermediate_pdfs(converted_pdfs)
        console.print("[green]Cleanup complete![/green]")

    console.print(Panel(
        f"[bold green]Download complete![/bold green]\n\n"
        f"Your files are in:\n{course_dir}\n\n"
        f"Combined PDF:\n{combined_path}" if combined_path else "",
        title="Success",
        border_style="green",
    ))

    # Offer to open the folder
    open_folder = questionary.confirm(
        "Open folder in Finder?",
        default=True,
    ).ask()

    if open_folder:
        subprocess.run(["open", str(course_dir)])


def main():
    """Main entry point."""
    print_banner()

    # Get or configure API client
    api = get_canvas_client()

    if not api:
        console.print("[yellow]Canvas is not configured.[/yellow]")
        api = configure_canvas()
        if not api:
            console.print("[red]Configuration cancelled. Exiting.[/red]")
            sys.exit(1)

    # Main menu loop
    while True:
        # Select a course
        course = select_course(api)

        if not course:
            console.print("\n[dim]Goodbye![/dim]")
            break

        # Select output directory
        output_dir = select_output_directory()

        if not output_dir:
            console.print("[yellow]No output directory selected.[/yellow]")
            continue

        # Confirm before starting
        console.print()
        confirm = questionary.confirm(
            f"Download '{course.get('name')}'?",
            default=True,
        ).ask()

        if confirm:
            try:
                run_download(api, course, output_dir)
            except KeyboardInterrupt:
                console.print("\n[yellow]Download cancelled.[/yellow]")
            except Exception as e:
                console.print(f"\n[red]An error occurred: {e}[/red]")

        # Ask if user wants to download another course
        console.print()
        another = questionary.confirm(
            "Download another course?",
            default=False,
        ).ask()

        if not another:
            console.print("\n[dim]Goodbye![/dim]")
            break


if __name__ == "__main__":
    main()
