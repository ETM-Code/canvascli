"""Canvas LMS API client."""

import os
import re
from pathlib import Path

import requests


# Default timeouts: (connect, read) in seconds
DEFAULT_TIMEOUT = (10, 60)
DOWNLOAD_TIMEOUT = (10, 300)  # Longer timeout for file downloads


class CanvasAPI:
    """Client for interacting with Canvas LMS API."""

    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1"
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        })

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Make a GET request to the API."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def _get_paginated(self, endpoint: str, params: dict | None = None) -> list:
        """Get all pages of a paginated endpoint."""
        params = params or {}
        params["per_page"] = 100
        results = []
        url = f"{self.api_base}/{endpoint.lstrip('/')}"

        while url:
            response = self.session.get(
                url,
                params=params if url.startswith(self.api_base) else None,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)

            # Check for next page in Link header
            link_header = response.headers.get("Link", "")
            url = None
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    match = re.search(r'<([^>]+)>', link)
                    if match:
                        url = match.group(1)
                    break
            params = None  # Only use params for first request

        return results

    def get_courses(self, include_favorites: bool = True) -> list[dict]:
        """Get list of courses for the current user."""
        params = {"enrollment_state": "active"}
        if include_favorites:
            params["include[]"] = "favorites"
        return self._get_paginated("courses", params)

    def get_favorite_courses(self) -> list[dict]:
        """Get list of favorite courses for the current user."""
        return self._get_paginated("users/self/favorites/courses")

    def get_course(self, course_id: int) -> dict:
        """Get a specific course."""
        return self._get(f"courses/{course_id}")

    def get_modules(self, course_id: int, include_items: bool = True) -> list[dict]:
        """Get modules for a course."""
        params = {}
        if include_items:
            params["include[]"] = "items"
        return self._get_paginated(f"courses/{course_id}/modules", params)

    def get_module_items(self, course_id: int, module_id: int) -> list[dict]:
        """Get items in a module."""
        return self._get_paginated(f"courses/{course_id}/modules/{module_id}/items")

    def get_files(self, course_id: int) -> list[dict]:
        """Get all files for a course."""
        return self._get_paginated(f"courses/{course_id}/files")

    def get_file(self, file_id: int) -> dict:
        """Get a specific file's metadata."""
        return self._get(f"files/{file_id}")

    def get_page(self, course_id: int, page_url: str) -> dict:
        """Get a wiki page by URL."""
        return self._get(f"courses/{course_id}/pages/{page_url}")

    def get_assignment(self, course_id: int, assignment_id: int) -> dict:
        """Get an assignment."""
        return self._get(f"courses/{course_id}/assignments/{assignment_id}")

    def get_discussion(self, course_id: int, discussion_id: int) -> dict:
        """Get a discussion topic."""
        return self._get(f"courses/{course_id}/discussion_topics/{discussion_id}")

    def get_quiz(self, course_id: int, quiz_id: int) -> dict:
        """Get a quiz."""
        return self._get(f"courses/{course_id}/quizzes/{quiz_id}")

    def download_file(self, file_url: str, dest_path: Path) -> Path:
        """Download a file from Canvas."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Follow redirects to get actual file
        response = self.session.get(
            file_url,
            stream=True,
            allow_redirects=True,
            timeout=DOWNLOAD_TIMEOUT,
        )
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return dest_path


def get_config_path() -> Path:
    """Get path to config file."""
    config_dir = Path.home() / ".config" / "canvascli"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config"


def load_config() -> dict:
    """Load configuration from file."""
    config_path = get_config_path()
    config = {}

    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()

    return config


def save_config(config: dict) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")


def get_canvas_client() -> CanvasAPI | None:
    """Get a configured Canvas API client, or None if not configured."""
    config = load_config()

    base_url = config.get("CANVAS_URL") or os.environ.get("CANVAS_URL")
    access_token = config.get("CANVAS_TOKEN") or os.environ.get("CANVAS_TOKEN")

    if not base_url or not access_token:
        return None

    return CanvasAPI(base_url, access_token)
