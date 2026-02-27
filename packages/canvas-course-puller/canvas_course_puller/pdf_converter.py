"""Convert various file types to PDF."""

import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Semaphore

from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .downloader import DownloadedItem, sanitize_filename


@dataclass
class ConvertedPDF:
    """A converted PDF with its module info."""
    path: Path
    module_name: str | None


# File extensions that can be converted
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}
HTML_EXTENSIONS = {".html", ".htm"}
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".css", ".json", ".xml", ".csv"}
PDF_EXTENSION = ".pdf"
DEFAULT_MAX_WORKERS = 4
MAX_WORKERS_CAP = 8
MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 0.75
MAX_CONCURRENT_OFFICE_CONVERSIONS = 2

class PDFConverter:
    """Converts various file types to PDF."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.pdf_dir = output_dir / "pdfs"
        self.console = Console()
        self._weasyprint_available = None
        self._libreoffice_available = None
        self._office_semaphore = Semaphore(MAX_CONCURRENT_OFFICE_CONVERSIONS)

    def check_dependencies(self) -> dict[str, bool]:
        """Check which conversion tools are available."""
        deps = {}

        try:
            from weasyprint import HTML
            deps["weasyprint"] = True
        except ImportError:
            deps["weasyprint"] = False

        try:
            result = subprocess.run(
                ["soffice", "--version"],
                capture_output=True,
                timeout=5,
            )
            deps["libreoffice"] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            deps["libreoffice"] = False

        return deps

    def convert_all(self, items: list[DownloadedItem]) -> list[ConvertedPDF]:
        """Convert all items to PDF."""
        if not items:
            return []

        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        converted_pdfs: list[ConvertedPDF] = []
        failed_conversions: list[str] = []

        deps = self.check_dependencies()
        if not deps.get("weasyprint"):
            self.console.print("[yellow]Warning: weasyprint not available, HTML conversion may fail[/yellow]")
        if not deps.get("libreoffice"):
            self.console.print("[yellow]Warning: LibreOffice not available, Office document conversion will be skipped[/yellow]")

        max_workers = self._determine_max_workers(len(items))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Converting to PDF", total=len(items))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._convert_item_with_retries, item, deps): item
                    for item in items
                }

                for future in as_completed(futures):
                    item = futures[future]
                    pdf_path: Path | None = None
                    error: str | None = None
                    source_name = item.source_path.name if item.source_path else item.title

                    try:
                        pdf_path, error = future.result()
                    except Exception as e:
                        error = str(e)

                    if pdf_path:
                        converted_pdfs.append(ConvertedPDF(path=pdf_path, module_name=item.module_name))
                    elif error:
                        failed_conversions.append(f"{source_name}: {error}")

                    progress.advance(task)

        self.console.print(f"\n[green]Converted {len(converted_pdfs)} items to PDF[/green]")
        if failed_conversions:
            self.console.print(
                f"[yellow]Failed to convert {len(failed_conversions)} items.[/yellow]"
            )
            for failure in failed_conversions[:5]:
                self.console.print(f"[dim]- {failure}[/dim]")
            if len(failed_conversions) > 5:
                self.console.print(f"[dim]...and {len(failed_conversions) - 5} more[/dim]")

        return converted_pdfs

    def _determine_max_workers(self, item_count: int) -> int:
        """Choose a safe amount of parallelism for conversions."""
        cpu_count = os.cpu_count() or DEFAULT_MAX_WORKERS
        target = max(1, min(cpu_count - 1, DEFAULT_MAX_WORKERS))
        workers = min(MAX_WORKERS_CAP, target, item_count)
        return max(1, workers)

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Detect transient errors worth retrying."""
        if isinstance(exc, (subprocess.TimeoutExpired, TimeoutError, MemoryError, OSError)):
            return True

        msg = str(exc).lower()
        retryable_fragments = (
            "429",
            "too many requests",
            "rate limit",
            "temporarily unavailable",
            "timeout",
            "timed out",
            "memory",
            "cannot allocate",
            "resource busy",
            "broken pipe",
        )
        return any(fragment in msg for fragment in retryable_fragments)

    def _convert_item_with_retries(
        self, item: DownloadedItem, deps: dict[str, bool]
    ) -> tuple[Path | None, str | None]:
        """Convert one item with bounded retries for transient errors."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._convert_item(item, deps), None
            except Exception as e:
                last_error = e
                if attempt == MAX_RETRIES or not self._is_retryable_error(e):
                    break

                sleep_seconds = BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                time.sleep(sleep_seconds)

        if last_error:
            return None, str(last_error)
        return None, "Unknown conversion error"

    def _convert_item(self, item: DownloadedItem, deps: dict[str, bool]) -> Path | None:
        """Convert a single item to PDF."""
        if not item.source_path or not item.source_path.exists():
            return None

        suffix = item.source_path.suffix.lower()

        try:
            relative = item.source_path.relative_to(self.output_dir)
            safe_name = sanitize_filename(str(relative.with_suffix("")).replace("/", "_").replace("\\", "_"))
        except ValueError:
            safe_name = item.source_path.stem
            if item.module_name:
                safe_name = f"{sanitize_filename(item.module_name)}_{safe_name}"

        pdf_path = self.pdf_dir / f"{safe_name}.pdf"

        if suffix == PDF_EXTENSION:
            import shutil
            shutil.copy(item.source_path, pdf_path)
            return pdf_path

        if suffix in HTML_EXTENSIONS:
            if deps.get("weasyprint"):
                return self._convert_html_to_pdf(item.source_path, pdf_path)
            return None

        if suffix in IMAGE_EXTENSIONS:
            return self._convert_image_to_pdf(item.source_path, pdf_path)

        if suffix in OFFICE_EXTENSIONS:
            if deps.get("libreoffice"):
                return self._convert_office_to_pdf(item.source_path, pdf_path)
            return None

        if suffix in TEXT_EXTENSIONS:
            return self._convert_text_to_pdf(item.source_path, pdf_path, deps)

        return None

    def _convert_html_to_pdf(self, html_path: Path, pdf_path: Path) -> Path | None:
        """Convert HTML to PDF using weasyprint."""
        from weasyprint import HTML

        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return pdf_path

    def _convert_image_to_pdf(self, image_path: Path, pdf_path: Path) -> Path | None:
        """Convert image to PDF using Pillow."""
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(str(pdf_path), "PDF", resolution=100.0)
        return pdf_path

    def _convert_office_to_pdf(self, office_path: Path, pdf_path: Path) -> Path | None:
        """Convert Office document to PDF using LibreOffice."""
        with self._office_semaphore:
            with tempfile.TemporaryDirectory() as temp_dir:
                result = subprocess.run(
                    [
                        "soffice",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", temp_dir,
                        str(office_path),
                    ],
                    capture_output=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    stderr = result.stderr.decode("utf-8", errors="replace").strip()
                    raise RuntimeError(stderr or "LibreOffice conversion failed")

                temp_pdf = Path(temp_dir) / f"{office_path.stem}.pdf"
                if temp_pdf.exists():
                    import shutil
                    shutil.move(str(temp_pdf), str(pdf_path))
                    return pdf_path

        raise RuntimeError(f"Converted PDF not found for {office_path.name}")

    def _convert_text_to_pdf(self, text_path: Path, pdf_path: Path, deps: dict[str, bool]) -> Path | None:
        """Convert text file to PDF via HTML."""
        if not deps.get("weasyprint"):
            return None

        import html
        content = text_path.read_text(encoding="utf-8", errors="replace")
        escaped_content = html.escape(content)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{text_path.name}</title>
    <style>
        body {{
            font-family: 'Courier New', Consolas, monospace;
            font-size: 10pt;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            line-height: 1.4;
        }}
        h1 {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            background: #f8f8f8;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <h1>{text_path.name}</h1>
    <pre>{escaped_content}</pre>
</body>
</html>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html_content)
            temp_html = Path(f.name)

        try:
            from weasyprint import HTML

            HTML(filename=str(temp_html)).write_pdf(str(pdf_path))
            return pdf_path
        finally:
            temp_html.unlink(missing_ok=True)
