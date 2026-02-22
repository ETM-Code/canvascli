---
name: canvas-dev
description: Develop, extend, and debug the Canvas CLI tools (canvascli, canvas-course-puller, canvas-api). Use when adding new CLI commands, extending the Canvas API client, fixing bugs, or understanding the codebase architecture.
---

# Canvas CLI Tools — Development Skill

## Project Overview

This is a **uv workspace monorepo** with three Python packages for interacting with Canvas LMS:

| Package | Path | Purpose | Entry Point |
|---------|------|---------|-------------|
| `canvas-api` | `packages/canvas-api/` | Shared API client library | imported as `canvas_api` |
| `canvascli` | `packages/canvascli/` | Full CLI (click-based, 13 command groups) | `canvascli` |
| `canvas-course-puller` | `packages/canvas-course-puller/` | Interactive bulk course downloader | `canvas-course-puller` |

Python 3.11+. Package manager: `uv`. Build backend: `hatchling`.

## Architecture

```
packages/
├── canvas-api/canvas_api/
│   ├── client.py          # CanvasAPI class — all HTTP methods + Canvas endpoints
│   └── config.py          # load_config, save_config, get_canvas_client
│
├── canvascli/canvascli/
│   ├── cli.py             # Root click group (@click.group), registers all commands
│   ├── context.py         # CanvasContext (shared state), pass_context decorator
│   ├── output.py          # output_table, output_detail, format_date, truncate
│   ├── confirm.py         # confirm_action — required for all mutating operations
│   └── commands/
│       ├── auth.py        # login (deep-link), status, logout
│       ├── courses.py     # list, view
│       ├── modules.py     # list, view
│       ├── assignments.py # list, view, submit [CONFIRM]
│       ├── files.py       # list, download, upload [CONFIRM]
│       ├── pages.py       # list, view (renders HTML via html2text)
│       ├── grades.py      # list (enrollments + submissions)
│       ├── announcements.py # list, view
│       ├── discussions.py # list, view, reply [CONFIRM]
│       ├── quizzes.py     # list, view
│       ├── todo.py        # single command (no subgroup)
│       ├── calendar.py    # single command (no subgroup)
│       └── pull.py        # wraps canvas-course-puller for non-interactive bulk download
│
└── canvas-course-puller/canvas_course_puller/
    ├── cli.py             # Interactive questionary-based UI
    ├── downloader.py      # CourseDownloader — parallel downloads (8 threads)
    ├── pdf_converter.py   # PDFConverter — HTML/image/Office/text → PDF
    └── pdf_combiner.py    # PDFCombiner — merge + deduplicate pages
```

## Key Patterns

### Adding a New CLI Command

1. **Add API method** in `packages/canvas-api/canvas_api/client.py`:
   ```python
   def get_new_thing(self, course_id: int) -> list[dict]:
       return self._get_paginated(f"courses/{course_id}/new_things")
   ```

2. **Create command file** at `packages/canvascli/canvascli/commands/new_thing.py`:
   ```python
   import click
   from ..context import pass_context
   from ..output import output_table, format_date

   @click.group()
   def new_thing():
       """Description for help text."""
       pass

   @new_thing.command("list")
   @click.option("--course", "course_id", type=int, default=None)
   @pass_context
   def list_items(ctx, course_id):
       api = ctx.require_auth()
       cid = course_id or ctx.require_course()
       data = api.get_new_thing(cid)
       # Format and display...
       output_table(rows, columns, ctx)
   ```

3. **Register** in `packages/canvascli/canvascli/cli.py` inside `register_commands()`:
   ```python
   from .commands import new_thing
   cli.add_command(new_thing.new_thing)
   ```

4. **Rebuild**: `uv sync --all-packages`

### Command Conventions

- **Read-only commands** (list, view, download): no confirmation needed
- **Mutating commands** (submit, upload, reply, delete): MUST use `confirm_action()` from `confirm.py`
- Every command that needs a course uses `@click.option("--course", ...)` AND checks `ctx.require_course()` as fallback to the global `--course` flag
- Every command starts with `api = ctx.require_auth()` to get the authenticated API client
- Support `--json` output: use `output_table()` / `output_detail()` which check `ctx.json_output`
- HTML content from Canvas should be rendered via `html2text` for terminal display

### CanvasAPI Client Pattern

```python
# GET single item
def get_thing(self, id: int) -> dict:
    return self._get(f"things/{id}")

# GET paginated list
def get_things(self, course_id: int) -> list[dict]:
    return self._get_paginated(f"courses/{course_id}/things")

# POST (create)
def create_thing(self, course_id: int, data: str) -> dict:
    return self._post(f"courses/{course_id}/things", json_data={"data": data})

# File upload (multi-step: request URL → upload → confirm)
# See submit_assignment() or upload_file() for the pattern
```

Available HTTP methods: `_get`, `_get_paginated`, `_post`, `_put`, `_delete`.
All handle auth headers, timeouts, and JSON parsing automatically.

### Canvas API Reference

Base URL pattern: `{canvas_url}/api/v1/{endpoint}`
Auth: Bearer token in Authorization header.
Pagination: Link header with `rel="next"`. Handled by `_get_paginated()`.
Canvas API docs: `https://canvas.instructure.com/doc/api/`

### Output Helpers

| Function | Use |
|----------|-----|
| `output_table(rows, columns, ctx)` | List data as rich table or JSON |
| `output_detail(data, fields, ctx)` | Single item as key-value panel or JSON |
| `format_date(iso_string)` | ISO → "Feb 22, 2026 11:59 PM" |
| `truncate(text, max_len)` | Truncate with ellipsis |
| `console` (from output.py) | Rich Console instance for direct printing |

### Configuration

Credentials stored at `~/.config/canvascli/config` as key=value:
```
CANVAS_URL=https://canvas.university.edu
CANVAS_TOKEN=your-token-here
```
Also reads `CANVAS_URL` and `CANVAS_TOKEN` environment variables as fallback.

### Circular Import Prevention

`cli.py` imports commands inside `register_commands()` (called after `cli` group is defined).
Commands import `pass_context` and `CanvasContext` from `context.py`, NOT from `cli.py`.

## Common Tasks

### Run the CLI
```bash
uv run canvascli --help
uv run canvascli courses list
uv run canvascli --json --course 12345 assignments list
```

### Run the course puller
```bash
uv run canvas-course-puller
```

### Sync after changes
```bash
uv sync --all-packages
```

### Test a specific API call
```python
from canvas_api import get_canvas_client
api = get_canvas_client()
print(api.get_courses())
```

## Dependencies

| Package | canvas-api | canvascli | canvas-course-puller |
|---------|-----------|-----------|---------------------|
| requests | x | | |
| click | | x | |
| rich | | x | x |
| rich-click | | x | |
| html2text | | x | |
| questionary | | | x |
| weasyprint | | | x |
| pypdf | | | x |
| Pillow | | | x |
| beautifulsoup4 | | | x |
