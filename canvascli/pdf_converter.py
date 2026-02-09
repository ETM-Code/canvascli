"""Convert various file types to PDF."""

import io
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .downloader import DownloadedItem


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

class PDFConverter:
    """Converts various file types to PDF."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.pdf_dir = output_dir / "pdfs"
        self.console = Console()
        self._weasyprint_available = None
        self._libreoffice_available = None

    def check_dependencies(self) -> dict[str, bool]:
        """Check which conversion tools are available."""
        deps = {}

        # Check weasyprint
        try:
            from weasyprint import HTML
            deps["weasyprint"] = True
        except ImportError:
            deps["weasyprint"] = False

        # Check LibreOffice
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
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        converted_pdfs = []

        deps = self.check_dependencies()
        if not deps.get("weasyprint"):
            self.console.print("[yellow]Warning: weasyprint not available, HTML conversion may fail[/yellow]")
        if not deps.get("libreoffice"):
            self.console.print("[yellow]Warning: LibreOffice not available, Office document conversion will be skipped[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Converting to PDF", total=len(items))

            for item in items:
                pdf_path = self._convert_item(item, deps)
                if pdf_path:
                    converted_pdfs.append(ConvertedPDF(path=pdf_path, module_name=item.module_name))
                progress.advance(task)

        self.console.print(f"\n[green]Converted {len(converted_pdfs)} items to PDF[/green]")
        return converted_pdfs

    def _convert_item(self, item: DownloadedItem, deps: dict[str, bool]) -> Path | None:
        """Convert a single item to PDF."""
        if not item.source_path or not item.source_path.exists():
            return None

        suffix = item.source_path.suffix.lower()

        # Create unique PDF name from relative path to avoid collisions
        from .downloader import sanitize_filename
        try:
            relative = item.source_path.relative_to(self.output_dir)
            safe_name = sanitize_filename(str(relative.with_suffix("")).replace("/", "_").replace("\\", "_"))
        except ValueError:
            # Fallback if path is not relative to output_dir
            safe_name = item.source_path.stem
            if item.module_name:
                safe_name = f"{sanitize_filename(item.module_name)}_{safe_name}"

        pdf_path = self.pdf_dir / f"{safe_name}.pdf"

        try:
            if suffix == PDF_EXTENSION:
                # Already a PDF, just copy
                import shutil
                shutil.copy(item.source_path, pdf_path)
                return pdf_path

            elif suffix in HTML_EXTENSIONS:
                if deps.get("weasyprint"):
                    return self._convert_html_to_pdf(item.source_path, pdf_path)
                return None

            elif suffix in IMAGE_EXTENSIONS:
                return self._convert_image_to_pdf(item.source_path, pdf_path)

            elif suffix in OFFICE_EXTENSIONS:
                if deps.get("libreoffice"):
                    return self._convert_office_to_pdf(item.source_path, pdf_path)
                return None

            elif suffix in TEXT_EXTENSIONS:
                # Convert text to HTML then to PDF
                return self._convert_text_to_pdf(item.source_path, pdf_path, deps)

        except Exception as e:
            self.console.print(f"[red]Error converting {item.source_path.name}: {e}[/red]")

        return None

    def _convert_html_to_pdf(self, html_path: Path, pdf_path: Path) -> Path | None:
        """Convert HTML to PDF using weasyprint."""
        try:
            from weasyprint import HTML
            HTML(filename=str(html_path)).write_pdf(str(pdf_path))
            return pdf_path
        except Exception as e:
            self.console.print(f"[red]HTML conversion failed: {e}[/red]")
            return None

    def _convert_image_to_pdf(self, image_path: Path, pdf_path: Path) -> Path | None:
        """Convert image to PDF using Pillow."""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                img.save(str(pdf_path), "PDF", resolution=100.0)
            return pdf_path
        except Exception as e:
            self.console.print(f"[red]Image conversion failed: {e}[/red]")
            return None

    def _convert_office_to_pdf(self, office_path: Path, pdf_path: Path) -> Path | None:
        """Convert Office document to PDF using LibreOffice."""
        try:
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
                    return None

                # Find the generated PDF
                temp_pdf = Path(temp_dir) / f"{office_path.stem}.pdf"
                if temp_pdf.exists():
                    import shutil
                    shutil.move(str(temp_pdf), str(pdf_path))
                    return pdf_path

        except Exception as e:
            self.console.print(f"[red]Office conversion failed: {e}[/red]")

        return None

    def _convert_text_to_pdf(self, text_path: Path, pdf_path: Path, deps: dict[str, bool]) -> Path | None:
        """Convert text file to PDF via HTML."""
        if not deps.get("weasyprint"):
            return None

        try:
            import html
            content = text_path.read_text(encoding="utf-8", errors="replace")
            escaped_content = html.escape(content)

            # Create HTML with proper formatting for code/text
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

            # Write temp HTML and convert
            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(html_content)
                temp_html = Path(f.name)

            try:
                from weasyprint import HTML
                HTML(filename=str(temp_html)).write_pdf(str(pdf_path))
                return pdf_path
            finally:
                temp_html.unlink(missing_ok=True)

        except Exception as e:
            self.console.print(f"[red]Text conversion failed: {e}[/red]")

        return None
