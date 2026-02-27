"""Download content from Canvas courses."""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from canvas_api import CanvasAPI

# Number of parallel download threads
MAX_WORKERS = 8
MODULE_FETCH_WORKERS = 4
MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 0.75


@dataclass
class DownloadedItem:
    """Represents a downloaded item."""
    title: str
    item_type: str
    source_path: Path | None  # Path to downloaded file
    html_content: str | None  # HTML content for pages
    module_name: str | None  # Which module this came from


def sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip('. ')
    return name[:200]


class CourseDownloader:
    """Downloads content from a Canvas course."""

    def __init__(self, api: CanvasAPI, course_id: int, output_dir: Path):
        self.api = api
        self.course_id = course_id
        self.output_dir = output_dir
        self.console = Console()
        self.downloaded_items: list[DownloadedItem] = []
        self._downloaded_file_ids: set[int] = set()
        self._skipped_items: list[str] = []
        self._lock = Lock()

    def _add_downloaded_item(self, item: DownloadedItem, file_id: int | None = None) -> None:
        """Thread-safe add of downloaded item."""
        with self._lock:
            self.downloaded_items.append(item)
            if file_id is not None:
                self._downloaded_file_ids.add(file_id)

    def _add_skipped_item(self, description: str) -> None:
        """Thread-safe add of skipped item."""
        with self._lock:
            self._skipped_items.append(description)

    def _is_file_downloaded(self, file_id: int) -> bool:
        """Thread-safe check if file already downloaded."""
        with self._lock:
            return file_id in self._downloaded_file_ids

    def _mark_file_downloaded(self, file_id: int) -> bool:
        """Thread-safe mark file as downloaded. Returns False if already downloaded."""
        with self._lock:
            if file_id in self._downloaded_file_ids:
                return False
            self._downloaded_file_ids.add(file_id)
            return True

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Detect whether an error is likely transient."""
        message = str(exc).lower()
        retryable_markers = (
            "429",
            "too many requests",
            "rate limit",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
        )
        return any(marker in message for marker in retryable_markers)

    def _run_with_retries(self, fn, *args, **kwargs):
        """Run a callable with exponential backoff for transient failures."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == MAX_RETRIES or not self._is_retryable_error(e):
                    break
                time.sleep(BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)))

        if last_error:
            raise last_error
        raise RuntimeError("Unknown retry failure")

    def download_all(self) -> list[DownloadedItem]:
        """Download all content from modules and files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._download_modules()
        self._download_files()

        if self._skipped_items:
            self.console.print(f"\n[yellow]Skipped {len(self._skipped_items)} items (not accessible):[/yellow]")
            for item in self._skipped_items[:5]:
                self.console.print(f"  [dim]- {item}[/dim]")
            if len(self._skipped_items) > 5:
                self.console.print(f"  [dim]... and {len(self._skipped_items) - 5} more[/dim]")

        return self.downloaded_items

    def _download_modules(self) -> None:
        """Download content from all modules in parallel."""
        self.console.print("\n[bold blue]Fetching modules...[/bold blue]")
        modules = self._run_with_retries(self.api.get_modules, self.course_id, include_items=True)

        if not modules:
            self.console.print("[yellow]No modules found[/yellow]")
            return

        self.console.print(f"Found {len(modules)} modules")

        all_items: list[tuple[dict, str]] = []

        def expand_module(module: dict) -> list[tuple[dict, str]]:
            module_name = module.get("name", "Untitled Module")
            items = module.get("items", [])
            if not items:
                module_id = module.get("id")
                if module_id:
                    items = self._run_with_retries(self.api.get_module_items, self.course_id, module_id)
            return [(item, module_name) for item in items]

        with ThreadPoolExecutor(max_workers=min(MODULE_FETCH_WORKERS, len(modules))) as executor:
            futures = [executor.submit(expand_module, module) for module in modules]
            for future in as_completed(futures):
                try:
                    all_items.extend(future.result())
                except Exception:
                    continue

        if not all_items:
            self.console.print("[yellow]No items in modules[/yellow]")
            return

        self.console.print(f"Downloading {len(all_items)} items from modules...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Downloading module items", total=len(all_items))

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self._download_module_item, item, module_name): (item, module_name)
                    for item, module_name in all_items
                }

                for future in as_completed(futures):
                    progress.advance(task)

    def _download_module_item(self, item: dict, module_name: str) -> None:
        """Download a single module item."""
        item_type = item.get("type", "")
        title = item.get("title", "Untitled")
        content_id = item.get("content_id")

        safe_module = sanitize_filename(module_name)
        safe_title = sanitize_filename(title)
        module_dir = self.output_dir / "modules" / safe_module

        try:
            if item_type == "File" and content_id:
                file_info = self._run_with_retries(self.api.get_file, content_id)
                file_id = file_info.get("id")
                file_url = file_info.get("url")
                filename = file_info.get("filename", f"{safe_title}.bin")
                dest = module_dir / sanitize_filename(filename)

                if file_url and self._mark_file_downloaded(file_id):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    self._run_with_retries(self.api.download_file, file_url, dest)
                    self._add_downloaded_item(DownloadedItem(
                        title=title,
                        item_type="File",
                        source_path=dest,
                        html_content=None,
                        module_name=module_name,
                    ))
                elif not file_url:
                    self._add_skipped_item(f"File: {title} (no URL)")

            elif item_type == "Page":
                page_url = item.get("page_url")
                if page_url:
                    page = self._run_with_retries(self.api.get_page, self.course_id, page_url)
                    page_body = page.get("body", "")
                    page_title = page.get("title", title)

                    self._extract_and_download_linked_files(
                        page_body, module_dir, module_name
                    )

                    html_content = self._wrap_html(page_body, page_title)
                    dest = module_dir / f"{safe_title}.html"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(html_content, encoding="utf-8")
                    self._add_downloaded_item(DownloadedItem(
                        title=title,
                        item_type="Page",
                        source_path=dest,
                        html_content=html_content,
                        module_name=module_name,
                    ))

            elif item_type == "Assignment" and content_id:
                assignment = self._run_with_retries(self.api.get_assignment, self.course_id, content_id)
                html_content = self._format_assignment_html(assignment)
                dest = module_dir / f"{safe_title}.html"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(html_content, encoding="utf-8")
                self._add_downloaded_item(DownloadedItem(
                    title=title,
                    item_type="Assignment",
                    source_path=dest,
                    html_content=html_content,
                    module_name=module_name,
                ))

            elif item_type == "Discussion" and content_id:
                discussion = self._run_with_retries(self.api.get_discussion, self.course_id, content_id)
                html_content = self._format_discussion_html(discussion)
                dest = module_dir / f"{safe_title}.html"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(html_content, encoding="utf-8")
                self._add_downloaded_item(DownloadedItem(
                    title=title,
                    item_type="Discussion",
                    source_path=dest,
                    html_content=html_content,
                    module_name=module_name,
                ))

            elif item_type == "Quiz" and content_id:
                try:
                    quiz = self._run_with_retries(self.api.get_quiz, self.course_id, content_id)
                    html_content = self._format_quiz_html(quiz)
                    dest = module_dir / f"{safe_title}.html"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(html_content, encoding="utf-8")
                    self._add_downloaded_item(DownloadedItem(
                        title=title,
                        item_type="Quiz",
                        source_path=dest,
                        html_content=html_content,
                        module_name=module_name,
                    ))
                except Exception:
                    self._add_skipped_item(f"Quiz: {title}")

            elif item_type == "ExternalUrl":
                external_url = item.get("external_url", "")
                html_content = self._format_external_url_html(title, external_url)
                dest = module_dir / f"{safe_title}.html"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(html_content, encoding="utf-8")
                self._add_downloaded_item(DownloadedItem(
                    title=title,
                    item_type="ExternalUrl",
                    source_path=dest,
                    html_content=html_content,
                    module_name=module_name,
                ))

            elif item_type == "SubHeader":
                pass

        except Exception:
            self._add_skipped_item(f"{item_type}: {title}")

    def _download_files(self) -> None:
        """Download all files from the course files section."""
        self.console.print("\n[bold blue]Fetching course files...[/bold blue]")

        try:
            files = self._run_with_retries(self.api.get_files, self.course_id)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                self.console.print("[yellow]Course files not accessible (restricted by instructor)[/yellow]")
                self.console.print("[dim]Files from modules were still downloaded above[/dim]")
            else:
                self.console.print(f"[yellow]Could not fetch course files: {e}[/yellow]")
            return

        if not files:
            self.console.print("[yellow]No additional files found[/yellow]")
            return

        self.console.print(f"Found {len(files)} files")
        files_dir = self.output_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        def download_single_file(file_info: dict) -> None:
            try:
                file_id = file_info.get("id")
                file_url = file_info.get("url")
                filename = file_info.get("filename", file_info.get("display_name", "file"))
                title = file_info.get("display_name", filename)
                dest = files_dir / sanitize_filename(filename)

                if file_url and self._mark_file_downloaded(file_id):
                    self._run_with_retries(self.api.download_file, file_url, dest)
                    self._add_downloaded_item(DownloadedItem(
                        title=title,
                        item_type="File",
                        source_path=dest,
                        html_content=None,
                        module_name=None,
                    ))
            except Exception:
                self._add_skipped_item(f"File: {file_info.get('display_name', 'unknown')}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Downloading files", total=len(files))

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(download_single_file, f) for f in files]

                for future in as_completed(futures):
                    progress.advance(task)

    def _extract_and_download_linked_files(
        self, html_content: str, dest_dir: Path, module_name: str
    ) -> list[Path]:
        """Extract file links from HTML and download them."""
        downloaded = []
        if not html_content:
            return downloaded

        soup = BeautifulSoup(html_content, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            file_match = re.search(r"/files/(\d+)", href)
            if not file_match:
                continue

            file_id = int(file_match.group(1))
            if not self._mark_file_downloaded(file_id):
                continue

            try:
                file_info = self._run_with_retries(self.api.get_file, file_id)
                file_url = file_info.get("url")
                filename = file_info.get("filename", f"file_{file_id}")

                if file_url:
                    dest = dest_dir / sanitize_filename(filename)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    self._run_with_retries(self.api.download_file, file_url, dest)

                    self._add_downloaded_item(DownloadedItem(
                        title=file_info.get("display_name", filename),
                        item_type="File",
                        source_path=dest,
                        html_content=None,
                        module_name=module_name,
                    ))
                    downloaded.append(dest)

            except Exception:
                link_text = link.get_text(strip=True) or f"file_{file_id}"
                self._add_skipped_item(f"Linked file: {link_text}")

        return downloaded

    def _wrap_html(self, body: str, title: str) -> str:
        """Wrap HTML content in a full HTML document."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2, h3 {{ color: #34495e; }}
        a {{ color: #3498db; }}
        pre {{ background: #f4f4f4; padding: 15px; overflow-x: auto; border-radius: 5px; }}
        code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
        img {{ max-width: 100%; height: auto; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f4f4f4; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {body}
</body>
</html>"""

    def _format_assignment_html(self, assignment: dict) -> str:
        """Format an assignment as HTML."""
        title = assignment.get("name", "Assignment")
        description = assignment.get("description", "") or ""
        due_at = assignment.get("due_at", "No due date")
        points = assignment.get("points_possible", "N/A")

        body = f"""
        <div class="assignment-info">
            <p><strong>Due:</strong> {due_at}</p>
            <p><strong>Points:</strong> {points}</p>
        </div>
        <div class="description">
            {description}
        </div>
        """
        return self._wrap_html(body, title)

    def _format_discussion_html(self, discussion: dict) -> str:
        """Format a discussion topic as HTML."""
        title = discussion.get("title", "Discussion")
        message = discussion.get("message", "") or ""
        posted_at = discussion.get("posted_at", "")

        body = f"""
        <div class="discussion-info">
            <p><strong>Posted:</strong> {posted_at}</p>
        </div>
        <div class="message">
            {message}
        </div>
        """
        return self._wrap_html(body, title)

    def _format_quiz_html(self, quiz: dict) -> str:
        """Format a quiz as HTML."""
        title = quiz.get("title", "Quiz")
        description = quiz.get("description", "") or ""
        due_at = quiz.get("due_at", "No due date")
        points = quiz.get("points_possible", "N/A")
        time_limit = quiz.get("time_limit")
        time_str = f"{time_limit} minutes" if time_limit else "No time limit"

        body = f"""
        <div class="quiz-info">
            <p><strong>Due:</strong> {due_at}</p>
            <p><strong>Points:</strong> {points}</p>
            <p><strong>Time Limit:</strong> {time_str}</p>
        </div>
        <div class="description">
            {description}
        </div>
        """
        return self._wrap_html(body, title)

    def _format_external_url_html(self, title: str, url: str) -> str:
        """Format an external URL as HTML."""
        body = f"""
        <div class="external-link">
            <p>This is an external link:</p>
            <p><a href="{url}">{url}</a></p>
        </div>
        """
        return self._wrap_html(body, title)
