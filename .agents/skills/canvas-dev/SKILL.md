---
name: canvas
description: Interact with Canvas LMS from the terminal. Use when the user wants to check assignments, view grades, list courses, read announcements, download course content, view discussions, check quizzes, see todo items, or do anything related to their university Canvas account.
---

# Canvas CLI

Two tools for Canvas LMS are installed globally on this machine:

- `canvascli` — full CLI for browsing Canvas (courses, assignments, grades, files, etc.)
- `canvas-course-puller` — interactive bulk course downloader with PDF conversion

## Authentication

Already configured at `~/.config/canvascli/config`. To reconfigure:

```bash
canvascli auth login    # Opens browser to Canvas token page
canvascli auth status   # Check current connection
canvascli auth logout   # Remove credentials
```

## Quick Reference

### Courses

```bash
canvascli courses list                   # All courses (favorites marked with *)
canvascli courses list --favorites       # Favorites only
canvascli courses view 12345             # Course details
```

### Assignments

```bash
canvascli --course 12345 assignments list          # List with due dates & status
canvascli --course 12345 assignments view 67890    # Full details + description
canvascli --course 12345 assignments submit 67890 --file ./hw.pdf   # Submit (asks confirmation)
```

### Grades

```bash
canvascli --course 12345 grades list     # Course grade + per-assignment scores
```

### Files

```bash
canvascli --course 12345 files list              # List course files
canvascli files download 99999                   # Download a file by ID
canvascli files download 99999 -o ./myfile.pdf   # Download to specific path
canvascli --course 12345 files upload --file ./notes.pdf   # Upload (asks confirmation)
```

### Pages

```bash
canvascli --course 12345 pages list              # List wiki pages
canvascli --course 12345 pages view page-slug    # Read page content in terminal
```

### Modules

```bash
canvascli --course 12345 modules list            # List modules
canvascli --course 12345 modules view 11111      # View items in a module
```

### Announcements

```bash
canvascli --course 12345 announcements list      # List announcements
canvascli --course 12345 announcements view 222  # Read full announcement
```

### Discussions

```bash
canvascli --course 12345 discussions list                          # List topics
canvascli --course 12345 discussions view 333                      # View with replies
canvascli --course 12345 discussions reply 333 -m "My reply"       # Post reply (asks confirmation)
```

### Quizzes

```bash
canvascli --course 12345 quizzes list            # List quizzes
canvascli --course 12345 quizzes view 444        # Quiz details (due date, time limit, etc.)
```

### Todo & Calendar

```bash
canvascli todo                           # All pending todo items across courses
canvascli calendar                       # Next 14 days of events
canvascli calendar --days 30             # Next 30 days
```

### Bulk Download

```bash
canvascli --course 12345 pull                       # Download entire course
canvascli --course 12345 pull -o ./archive          # Custom output directory
canvascli --course 12345 pull --no-pdf              # Download only, skip PDF conversion
canvascli --course 12345 pull --no-combine          # Convert but don't merge into single PDF
canvas-course-puller                                # Interactive mode with course picker
```

## Global Options

| Flag | Effect |
|------|--------|
| `--json` | Output as JSON instead of tables (for scripting/piping) |
| `--course ID` | Set course context for all subcommands |
| `--version` | Show version |

The `--course` flag can be set globally or per-subcommand:
```bash
canvascli --course 12345 assignments list    # Global
canvascli assignments list --course 12345    # Per-command (same result)
```

## Tips

- Run `canvascli courses list` first to find course IDs
- Use `--json` to pipe output to `jq` or other tools: `canvascli --json todo | jq '.[] | .title'`
- Mutating actions (submit, upload, reply) always ask for confirmation before executing
- `canvas-course-puller` is better for bulk archiving whole courses interactively
- `canvascli pull` is better for scripted/non-interactive bulk downloads
