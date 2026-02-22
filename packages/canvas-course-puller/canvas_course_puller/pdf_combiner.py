"""Combine multiple PDFs into one."""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import questionary
from pypdf import PdfReader, PdfWriter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .pdf_converter import ConvertedPDF


LARGE_MODULE_THRESHOLD = 300  # Pages


@dataclass
class PDFInfo:
    """Information about a PDF file."""
    path: Path
    pages: int
    module_name: str | None = None
    reader: PdfReader | None = None


@dataclass
class ModuleInfo:
    """Information about a module's PDFs."""
    name: str
    pdfs: list[PDFInfo] = field(default_factory=list)
    total_pages: int = 0


class PDFCombiner:
    """Combines multiple PDF files into a single document."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.console = Console()
        self._failed_pdfs: list[str] = []

    def _get_pdf_info(self, converted_pdfs: list[ConvertedPDF]) -> list[PDFInfo]:
        """Get page counts for all PDFs."""
        logging.getLogger("pypdf").setLevel(logging.ERROR)

        infos = []
        for converted in converted_pdfs:
            try:
                reader = PdfReader(str(converted.path), strict=False)
                infos.append(PDFInfo(
                    path=converted.path,
                    pages=len(reader.pages),
                    module_name=converted.module_name,
                    reader=reader,
                ))
            except Exception:
                self._failed_pdfs.append(converted.path.name)
        return infos

    def _group_by_module(self, pdf_infos: list[PDFInfo]) -> dict[str, ModuleInfo]:
        """Group PDFs by module and calculate total pages per module."""
        modules: dict[str, ModuleInfo] = {}

        for pdf_info in pdf_infos:
            module_name = pdf_info.module_name or "__files__"

            if module_name not in modules:
                modules[module_name] = ModuleInfo(name=module_name)

            modules[module_name].pdfs.append(pdf_info)
            modules[module_name].total_pages += pdf_info.pages

        return modules

    def _prompt_for_selection(self, pdf_infos: list[PDFInfo]) -> list[PDFInfo]:
        """Prompt user to select which modules to include if there are large ones."""
        modules = self._group_by_module(pdf_infos)

        large_modules = {k: v for k, v in modules.items() if v.total_pages >= LARGE_MODULE_THRESHOLD}
        small_modules = {k: v for k, v in modules.items() if v.total_pages < LARGE_MODULE_THRESHOLD}

        if not large_modules:
            return pdf_infos

        self.console.print(f"\n[yellow]Found {len(large_modules)} large modules (>{LARGE_MODULE_THRESHOLD} pages)[/yellow]")

        choices = []

        if small_modules:
            total_small_pages = sum(m.total_pages for m in small_modules.values())
            total_small_files = sum(len(m.pdfs) for m in small_modules.values())
            choices.append(questionary.Choice(
                title=f"All smaller modules ({len(small_modules)} modules, {total_small_files} files, {total_small_pages} pages)",
                value="__small__",
                checked=True,
            ))

        for module_name in sorted(large_modules.keys(), key=lambda k: large_modules[k].total_pages, reverse=True):
            module_info = large_modules[module_name]
            display_name = module_name if module_name != "__files__" else "Course Files"
            display_name = display_name[:50] + "..." if len(display_name) > 50 else display_name
            choices.append(questionary.Choice(
                title=f"{display_name} ({module_info.total_pages} pages, {len(module_info.pdfs)} files)",
                value=module_name,
                checked=True,
            ))

        selected = questionary.checkbox(
            "Select which modules to include in combined document:",
            choices=choices,
        ).ask()

        if selected is None:
            return pdf_infos

        result = []

        if "__small__" in selected:
            for module_info in small_modules.values():
                result.extend(module_info.pdfs)

        for module_name in large_modules:
            if module_name in selected:
                result.extend(large_modules[module_name].pdfs)

        return result

    def _compute_page_hash(self, page) -> str:
        """Compute a hash for a PDF page to detect duplicates."""
        try:
            text = page.extract_text() or ""
            mediabox = str(page.mediabox) if hasattr(page, 'mediabox') else ""
            content = f"{text}{mediabox}"
            return hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()
        except Exception:
            return f"unhashable_{id(page)}"

    def _remove_duplicate_pages(self, writer: PdfWriter) -> int:
        """Remove duplicate pages from the writer. Returns number of duplicates removed."""
        seen_hashes = {}
        pages_to_keep = []
        duplicates = 0

        for i, page in enumerate(writer.pages):
            page_hash = self._compute_page_hash(page)
            if page_hash not in seen_hashes:
                seen_hashes[page_hash] = i
                pages_to_keep.append(page)
            else:
                duplicates += 1

        if duplicates > 0:
            while len(writer.pages) > 0:
                del writer.pages[0]
            for page in pages_to_keep:
                writer.add_page(page)

        return duplicates

    def combine(self, converted_pdfs: list[ConvertedPDF], output_name: str = "combined_course_content.pdf") -> Path:
        """Combine all PDFs into a single file."""
        if not converted_pdfs:
            self.console.print("[yellow]No PDFs to combine[/yellow]")
            return None

        output_path = self.output_dir / output_name
        writer = PdfWriter()
        self._failed_pdfs = []

        logging.getLogger("pypdf").setLevel(logging.ERROR)

        self.console.print("\n[dim]Analyzing PDFs...[/dim]")
        pdf_infos = self._get_pdf_info(converted_pdfs)

        if not pdf_infos:
            self.console.print("[yellow]No readable PDFs found[/yellow]")
            return None

        selected_infos = self._prompt_for_selection(pdf_infos)

        if not selected_infos:
            self.console.print("[yellow]No PDFs selected[/yellow]")
            return None

        sorted_infos = sorted(selected_infos, key=lambda p: p.path.name.lower())

        self.console.print(f"\n[bold blue]Combining {len(sorted_infos)} PDFs...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Merging PDFs", total=len(sorted_infos))

            for pdf_info in sorted_infos:
                try:
                    reader = pdf_info.reader or PdfReader(str(pdf_info.path), strict=False)
                    for page in reader.pages:
                        writer.add_page(page)
                except Exception:
                    if pdf_info.path.name not in self._failed_pdfs:
                        self._failed_pdfs.append(pdf_info.path.name)

                progress.advance(task)

        self.console.print("[dim]Checking for duplicate pages...[/dim]")
        duplicates_removed = self._remove_duplicate_pages(writer)

        with open(output_path, "wb") as f:
            writer.write(f)

        total_pages = len(writer.pages)
        self.console.print(f"[green]Created combined PDF: {output_path.name} ({total_pages} pages)[/green]")

        if duplicates_removed > 0:
            self.console.print(f"[cyan]Removed {duplicates_removed} duplicate pages[/cyan]")

        if self._failed_pdfs:
            self.console.print(f"[yellow]Skipped {len(self._failed_pdfs)} unreadable PDFs[/yellow]")

        return output_path

    def cleanup_intermediate_pdfs(self, converted_pdfs: list[ConvertedPDF]) -> None:
        """Delete intermediate PDF files."""
        deleted = 0
        for converted in converted_pdfs:
            try:
                if converted.path.exists():
                    converted.path.unlink()
                    deleted += 1
            except Exception:
                pass

        self.console.print(f"[green]Deleted {deleted} intermediate PDF files[/green]")

        pdf_dir = self.output_dir / "pdfs"
        if pdf_dir.exists() and not any(pdf_dir.iterdir()):
            try:
                pdf_dir.rmdir()
            except Exception:
                pass
