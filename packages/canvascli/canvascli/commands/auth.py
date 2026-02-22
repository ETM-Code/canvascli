"""Auth commands: login, status, logout."""

import webbrowser

import click
from rich.console import Console
from rich.panel import Panel

from canvas_api import CanvasAPI, get_canvas_client, load_config, save_config, get_config_path

console = Console()


@click.group()
def auth():
    """Manage Canvas authentication."""
    pass


@auth.command()
def login():
    """Log in to Canvas by generating an API token."""
    console.print()

    # Check if already configured
    existing = get_canvas_client()
    if existing:
        try:
            user = existing.get_self()
            console.print(f"[yellow]Already logged in as {user.get('name', 'Unknown')}.[/yellow]")
            if not click.confirm("Reconfigure?", default=False):
                return
        except Exception:
            pass  # Token might be invalid, proceed with login

    # Step 1: Get Canvas URL
    canvas_url = click.prompt(
        "Canvas URL (e.g., https://canvas.university.edu)",
        type=str,
    )
    canvas_url = canvas_url.rstrip("/")

    if not canvas_url.startswith("http"):
        canvas_url = f"https://{canvas_url}"

    # Step 2: Open browser to token page
    token_url = f"{canvas_url}/profile/settings#access_tokens_holder"

    console.print(Panel(
        "1. Your browser will open to Canvas settings\n"
        "2. Scroll to [cyan]'Approved Integrations'[/cyan]\n"
        "3. Click [cyan]'+ New Access Token'[/cyan]\n"
        "4. Enter a purpose (e.g., 'Canvas CLI')\n"
        "5. Click [cyan]'Generate Token'[/cyan]\n"
        "6. [bold yellow]Copy the token[/bold yellow] (shown only once!)",
        title="Generate Access Token",
        border_style="blue",
    ))

    console.print(f"\n  Opening: {token_url}\n")
    webbrowser.open(token_url)

    # Step 3: Get the token
    access_token = click.prompt("Paste your access token", hide_input=True)

    if not access_token or len(access_token) < 10:
        console.print("[red]Invalid token.[/red]")
        return

    # Step 4: Validate
    console.print("[dim]Validating...[/dim]")
    try:
        api = CanvasAPI(canvas_url, access_token)
        user = api.get_self()
        name = user.get("name", "Unknown")
        console.print(f"[green]Authenticated as {name}[/green]")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        return

    # Step 5: Save
    save_config({
        "CANVAS_URL": canvas_url,
        "CANVAS_TOKEN": access_token,
    })
    console.print(f"[green]Credentials saved to {get_config_path()}[/green]")


@auth.command()
def status():
    """Show current authentication status."""
    config = load_config()
    url = config.get("CANVAS_URL")
    token = config.get("CANVAS_TOKEN")

    if not url or not token:
        console.print("[yellow]Not configured. Run 'canvascli auth login'.[/yellow]")
        return

    masked_token = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
    console.print(f"  URL:   {url}")
    console.print(f"  Token: {masked_token}")

    # Test the connection
    console.print("[dim]  Checking...[/dim]", end="")
    try:
        api = CanvasAPI(url, token)
        user = api.get_self()
        console.print(f"\r  User:  {user.get('name', 'Unknown')}  [green](valid)[/green]")
    except Exception:
        console.print("\r  [red]Token is invalid or expired.[/red]         ")


@auth.command()
def logout():
    """Remove saved Canvas credentials."""
    config_path = get_config_path()
    if config_path.exists():
        config_path.unlink()
        console.print("[green]Credentials removed.[/green]")
    else:
        console.print("[dim]No credentials to remove.[/dim]")
