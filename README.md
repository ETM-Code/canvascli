# canvascli

A command-line tool for downloading [Canvas LMS](https://www.instructure.com/canvas) course content and combining it into a single PDF.

Select a course, and canvascli will download all modules (pages, files, assignments, discussions, quizzes) and course files, convert everything to PDF, and merge it into one document.

## Features

- **Interactive course picker** with favorites shown first
- **Parallel downloads** for fast retrieval (8 threads)
- **Broad content support** &mdash; pages, files, assignments, discussions, quizzes, external links
- **Automatic PDF conversion** &mdash; HTML, images, Office docs, text/code files
- **Duplicate detection** &mdash; deduplicates files across modules and removes duplicate pages in the final PDF
- **Smart handling of large courses** &mdash; prompts to select/exclude large modules before combining
- **Browser-assisted setup** &mdash; opens Canvas settings to generate an access token on first run

## Installation

Requires **Python 3.11+**.

```bash
pip install -e .
```

For Office document conversion (`.docx`, `.xlsx`, `.pptx`), optionally install [LibreOffice](https://www.libreoffice.org/):

```bash
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt install libreoffice
```

For HTML-to-PDF conversion, you may also need system dependencies for [WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html):

```bash
# macOS
brew install pango

# Ubuntu/Debian
sudo apt install libpango-1.0-0 libpangocairo-1.0-0
```

## Usage

```bash
canvascli
```

On first run you'll be prompted to:

1. Enter your institution's Canvas URL (e.g. `https://canvas.university.edu`)
2. Generate an access token (the tool opens your browser to the right page)
3. Paste the token

Credentials are saved to `~/.config/canvascli/config`. You can also set them via environment variables:

```bash
export CANVAS_URL="https://canvas.university.edu"
export CANVAS_TOKEN="your-access-token"
```

### Workflow

1. Pick a course from the interactive menu
2. Choose an output directory (default: `./canvas_download`)
3. Wait for download, conversion, and PDF merging
4. Optionally remove intermediate PDFs
5. Open the output folder in Finder

### Output structure

```
canvas_download/
  Course_Name/
    modules/
      Module_1/
        page.html
        file.pdf
      Module_2/
        ...
    files/
      document.pdf
      image.png
    pdfs/
      (intermediate converted PDFs)
    Course_Name_complete.pdf   <- combined PDF
```

## Supported conversions

| Source type | Method |
|---|---|
| HTML / Wiki pages | WeasyPrint |
| Images (PNG, JPG, GIF, ...) | Pillow |
| Office docs (DOCX, XLSX, PPTX) | LibreOffice |
| Text / code files | HTML &rarr; WeasyPrint |
| PDF | Direct copy |

## License

[MIT](LICENSE)
