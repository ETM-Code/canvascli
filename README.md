# Canvas CLI Tools

Two CLI tools for [Canvas LMS](https://www.instructure.com/canvas): a full-featured CLI and a bulk course downloader.

## `canvascli` &mdash; Canvas from the terminal

Browse courses, check assignments, view grades, read announcements, and more &mdash; all without opening a browser.

```bash
canvascli courses list              # List your courses
canvascli --course 12345 todo       # View to-do items
canvascli assignments list          # See upcoming assignments
canvascli grades list               # Check your grades
canvascli pages view intro-page     # Read a wiki page
canvascli pull --course 12345       # Bulk download a whole course
```

### Commands

| Command | Description |
|---|---|
| `auth login` | Set up credentials (opens browser to Canvas token page) |
| `auth status` | Check current auth |
| `auth logout` | Remove saved credentials |
| `courses list` | List courses (`--favorites` for favorites only) |
| `courses view ID` | View course details |
| `modules list` | List modules |
| `modules view ID` | View module items |
| `assignments list` | List assignments with due dates and status |
| `assignments view ID` | View assignment details |
| `assignments submit ID --file PATH` | Submit a file (requires confirmation) |
| `files list` | List course files |
| `files download ID` | Download a file |
| `files upload --file PATH` | Upload a file (requires confirmation) |
| `pages list` | List wiki pages |
| `pages view SLUG` | View page content in terminal |
| `grades list` | View your grades |
| `announcements list` | List announcements |
| `announcements view ID` | Read an announcement |
| `discussions list` | List discussion topics |
| `discussions view ID` | View discussion with replies |
| `discussions reply ID -m TEXT` | Post a reply (requires confirmation) |
| `quizzes list` | List quizzes |
| `quizzes view ID` | View quiz details |
| `todo` | View your to-do items |
| `calendar` | View upcoming events (`--days N`) |
| `pull` | Bulk download a course |

**Global options:** `--json` for JSON output, `--course ID` to set course context.

## `canvas-course-puller` &mdash; Bulk course archiving

Download **everything** from a Canvas course in one shot. Interactive course picker, parallel downloads, automatic PDF conversion, and deduplication.

```bash
canvas-course-puller
```

- Downloads all modules (pages, files, assignments, discussions, quizzes) and course files
- Converts everything to PDF (HTML, images, Office docs, text/code)
- Merges into a single combined PDF
- Smart duplicate detection across modules
- Prompts for large modules before combining

## Installation

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages
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

## Setup

```bash
canvascli auth login
```

This opens your browser to Canvas settings where you generate an access token. Paste it back in the CLI and you're set. Credentials are saved to `~/.config/canvascli/config`.

You can also use environment variables:

```bash
export CANVAS_URL="https://canvas.university.edu"
export CANVAS_TOKEN="your-access-token"
```

## Project structure

```
packages/
  canvas-api/            # Shared Canvas API client library
  canvascli/             # Full CLI tool
  canvas-course-puller/  # Bulk download tool
```

## License

[MIT](LICENSE)
