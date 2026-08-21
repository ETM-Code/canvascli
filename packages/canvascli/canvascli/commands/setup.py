"""Guided setup command - checks environment and walks through configuration."""

import shutil
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from canvas_api import get_canvas_client, get_config_path

console = Console()


def _check_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = v >= (3, 11)
    return ok, f"{v.major}.{v.minor}.{v.micro}"


def _check_weasyprint() -> tuple[bool, str]:
    try:
        from weasyprint import __version__ as ver
        return True, ver
    except ImportError:
        return False, "not installed"
    except OSError as e:
        # WeasyPrint installed but system libs missing (Pango/Cairo/GTK)
        return False, f"missing system libraries: {e}"


def _check_libreoffice() -> tuple[bool, str]:
    from canvas_course_puller.pdf_converter import _find_soffice
    path = _find_soffice()
    if not path:
        return False, "not found"
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            # Parse "LibreOffice 24.8.4.2 ..." format
            parts = result.stdout.strip().split()
            ver = parts[1] if len(parts) >= 2 else "found"
            return True, ver
    except Exception:
        pass
    return False, "found but not working"


def _check_canvas_auth() -> tuple[bool, str]:
    client = get_canvas_client()
    if not client:
        return False, "not configured"
    try:
        user = client.get_self()
        return True, user.get("name", "authenticated")
    except Exception:
        return False, "token invalid or expired"


@click.command()
def setup():
    """Check your environment and set up canvascli step by step."""
    console.print()
    console.print(Panel(
        "[bold]canvascli setup[/bold]\n\n"
        "This will check your environment and walk you through configuration.",
        border_style="blue",
    ))

    # --- Dependency checks ---
    table = Table(title="Environment Check", show_header=True)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    checks = [
        ("Python 3.11+", _check_python),
        ("Canvas Auth", _check_canvas_auth),
        ("WeasyPrint (HTML to PDF)", _check_weasyprint),
        ("LibreOffice (Office to PDF)", _check_libreoffice),
    ]

    results = {}
    for name, check_fn in checks:
        ok, detail = check_fn()
        results[name] = ok
        status = "[green]OK[/green]" if ok else "[yellow]Missing[/yellow]"
        table.add_row(name, status, detail)

    console.print()
    console.print(table)
    console.print()

    # --- Guided fixes ---
    if not results["Canvas Auth"]:
        console.print("[bold yellow]Canvas is not configured.[/bold yellow]")
        if click.confirm("Set up Canvas authentication now?", default=True):
            from .auth import login
            ctx = click.Context(login)
            ctx.invoke(login)
            console.print()

    if not results["WeasyPrint (HTML to PDF)"]:
        console.print(Panel(
            _weasyprint_install_guide(),
            title="Install WeasyPrint",
            border_style="yellow",
        ))

    if not results["LibreOffice (Office to PDF)"]:
        console.print(Panel(
            _libreoffice_install_guide(),
            title="Install LibreOffice (optional)",
            border_style="yellow",
        ))

    # Re-check after potential fixes
    all_ok = all(results.values())
    if all_ok:
        console.print("[bold green]Everything looks good! You're ready to go.[/bold green]")
    else:
        console.print("[dim]Re-run 'canvascli setup' after installing missing components.[/dim]")

    console.print()
    console.print(f"[dim]Config file: {get_config_path()}[/dim]")


def _weasyprint_install_guide() -> str:
    if sys.platform == "win32":
        return (
            "[bold]WeasyPrint requires GTK3 libraries on Windows.[/bold]\n\n"
            "Option 1 (recommended): Install via MSYS2\n"
            "  1. Install MSYS2 from https://www.msys2.org/\n"
            "  2. In MSYS2 terminal run:\n"
            "     [cyan]pacman -S mingw-w64-x86_64-pango[/cyan]\n"
            "  3. Add MSYS2's mingw64/bin to your PATH\n\n"
            "Option 2: Install via conda\n"
            "  [cyan]conda install -c conda-forge weasyprint[/cyan]\n\n"
            "Then: [cyan]pip install weasyprint[/cyan]"
        )
    elif sys.platform == "darwin":
        return (
            "Install via Homebrew:\n"
            "  [cyan]brew install pango[/cyan]\n"
            "  [cyan]pip install weasyprint[/cyan]"
        )
    else:
        return (
            "Install system libraries:\n"
            "  [cyan]sudo apt install libpango-1.0-0 libpangocairo-1.0-0[/cyan]  (Debian/Ubuntu)\n"
            "  [cyan]sudo dnf install pango[/cyan]  (Fedora)\n\n"
            "Then: [cyan]pip install weasyprint[/cyan]"
        )


def _libreoffice_install_guide() -> str:
    if sys.platform == "win32":
        return (
            "[bold]LibreOffice converts Office documents (.docx, .xlsx, .pptx) to PDF.[/bold]\n\n"
            "1. Download from https://www.libreoffice.org/download/\n"
            "2. Install with default settings\n"
            "3. canvascli will find it automatically in Program Files\n\n"
            "[dim]Or add it to PATH manually:[/dim]\n"
            '  [cyan]$env:PATH += ";C:\\Program Files\\LibreOffice\\program"[/cyan]'
        )
    elif sys.platform == "darwin":
        return (
            "Install via Homebrew:\n"
            "  [cyan]brew install --cask libreoffice[/cyan]\n\n"
            "Or download from https://www.libreoffice.org/download/"
        )
    else:
        return (
            "Install via package manager:\n"
            "  [cyan]sudo apt install libreoffice[/cyan]  (Debian/Ubuntu)\n"
            "  [cyan]sudo dnf install libreoffice[/cyan]  (Fedora)"
        )
