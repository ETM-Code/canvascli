"""Canvas LMS API client."""

import re
from datetime import datetime, timedelta
from pathlib import Path

import requests


# Default timeouts: (connect, read) in seconds
DEFAULT_TIMEOUT = (10, 60)
DOWNLOAD_TIMEOUT = (10, 300)


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

    def _post(self, endpoint: str, data: dict | None = None, json_data: dict | None = None) -> dict:
        """Make a POST request to the API."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        response = self.session.post(url, data=data, json=json_data, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, data: dict | None = None, json_data: dict | None = None) -> dict:
        """Make a PUT request to the API."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        response = self.session.put(url, data=data, json=json_data, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def _delete(self, endpoint: str) -> dict:
        """Make a DELETE request to the API."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        response = self.session.delete(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    # ── User ──────────────────────────────────────────────────────────

    def get_self(self) -> dict:
        """Get current user profile."""
        return self._get("users/self")

    # ── Courses ───────────────────────────────────────────────────────

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
        return self._get(f"courses/{course_id}", params={"include[]": "total_students"})

    # ── Modules ───────────────────────────────────────────────────────

    def get_modules(self, course_id: int, include_items: bool = True) -> list[dict]:
        """Get modules for a course."""
        params = {}
        if include_items:
            params["include[]"] = "items"
        return self._get_paginated(f"courses/{course_id}/modules", params)

    def get_module_items(self, course_id: int, module_id: int) -> list[dict]:
        """Get items in a module."""
        return self._get_paginated(f"courses/{course_id}/modules/{module_id}/items")

    # ── Assignments ───────────────────────────────────────────────────

    def get_assignments(self, course_id: int) -> list[dict]:
        """Get all assignments for a course."""
        return self._get_paginated(
            f"courses/{course_id}/assignments",
            params={"include[]": "submission"},
        )

    def get_assignment(self, course_id: int, assignment_id: int) -> dict:
        """Get an assignment."""
        return self._get(
            f"courses/{course_id}/assignments/{assignment_id}",
            params={"include[]": "submission"},
        )

    def submit_assignment(self, course_id: int, assignment_id: int, file_path: Path) -> dict:
        """Submit a file to an assignment (multi-step upload process)."""
        # Step 1: Request upload URL
        file_size = file_path.stat().st_size
        upload_params = self._post(
            f"courses/{course_id}/assignments/{assignment_id}/submissions/self/files",
            json_data={
                "name": file_path.name,
                "size": file_size,
                "content_type": "application/octet-stream",
            },
        )

        # Step 2: Upload the file to the provided URL
        upload_url = upload_params["upload_url"]
        upload_data = upload_params.get("upload_params", {})
        with open(file_path, "rb") as f:
            response = requests.post(
                upload_url,
                data=upload_data,
                files={"file": (file_path.name, f)},
                timeout=DOWNLOAD_TIMEOUT,
            )
            response.raise_for_status()
            file_result = response.json()

        # Step 3: Create the submission with the uploaded file
        return self._post(
            f"courses/{course_id}/assignments/{assignment_id}/submissions",
            json_data={
                "submission": {
                    "submission_type": "online_upload",
                    "file_ids": [file_result["id"]],
                },
            },
        )

    # ── Files ─────────────────────────────────────────────────────────

    def get_files(self, course_id: int) -> list[dict]:
        """Get all files for a course."""
        return self._get_paginated(f"courses/{course_id}/files")

    def get_file(self, file_id: int) -> dict:
        """Get a specific file's metadata."""
        return self._get(f"files/{file_id}")

    def upload_file(self, course_id: int, file_path: Path, parent_folder_path: str = "/") -> dict:
        """Upload a file to a course's files section."""
        file_size = file_path.stat().st_size

        # Step 1: Notify Canvas about the upload
        upload_params = self._post(
            f"courses/{course_id}/files",
            json_data={
                "name": file_path.name,
                "size": file_size,
                "parent_folder_path": parent_folder_path,
            },
        )

        # Step 2: Upload the file
        upload_url = upload_params["upload_url"]
        upload_data = upload_params.get("upload_params", {})
        with open(file_path, "rb") as f:
            response = requests.post(
                upload_url,
                data=upload_data,
                files={"file": (file_path.name, f)},
                timeout=DOWNLOAD_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

    def download_file(self, file_url: str, dest_path: Path) -> Path:
        """Download a file from Canvas."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)

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

    # ── Pages ─────────────────────────────────────────────────────────

    def get_pages(self, course_id: int) -> list[dict]:
        """Get all wiki pages for a course."""
        return self._get_paginated(f"courses/{course_id}/pages")

    def get_page(self, course_id: int, page_url: str) -> dict:
        """Get a wiki page by URL slug."""
        return self._get(f"courses/{course_id}/pages/{page_url}")

    # ── Grades / Enrollments ──────────────────────────────────────────

    def get_enrollments(self, course_id: int, user_id: str = "self") -> list[dict]:
        """Get enrollments (includes grades) for a user in a course."""
        return self._get_paginated(
            f"courses/{course_id}/enrollments",
            params={"user_id": user_id, "include[]": "current_points"},
        )

    def get_submissions(self, course_id: int, user_id: str = "self") -> list[dict]:
        """Get all submissions for a user in a course."""
        return self._get_paginated(
            f"courses/{course_id}/students/submissions",
            params={"student_ids[]": user_id, "include[]": "assignment"},
        )

    # ── Announcements ─────────────────────────────────────────────────

    def get_announcements(self, course_id: int) -> list[dict]:
        """Get announcements for a course."""
        return self._get_paginated(
            "announcements",
            params={"context_codes[]": f"course_{course_id}"},
        )

    # ── Discussions ───────────────────────────────────────────────────

    def get_discussions(self, course_id: int) -> list[dict]:
        """Get discussion topics for a course."""
        return self._get_paginated(f"courses/{course_id}/discussion_topics")

    def get_discussion(self, course_id: int, discussion_id: int) -> dict:
        """Get a discussion topic."""
        return self._get(f"courses/{course_id}/discussion_topics/{discussion_id}")

    def get_discussion_entries(self, course_id: int, topic_id: int) -> list[dict]:
        """Get entries (replies) for a discussion topic."""
        return self._get_paginated(
            f"courses/{course_id}/discussion_topics/{topic_id}/entries"
        )

    def create_discussion_entry(self, course_id: int, topic_id: int, message: str) -> dict:
        """Post a reply to a discussion topic."""
        return self._post(
            f"courses/{course_id}/discussion_topics/{topic_id}/entries",
            json_data={"message": message},
        )

    # ── Quizzes ───────────────────────────────────────────────────────

    def get_quizzes(self, course_id: int) -> list[dict]:
        """Get all quizzes for a course."""
        return self._get_paginated(f"courses/{course_id}/quizzes")

    def get_quiz(self, course_id: int, quiz_id: int) -> dict:
        """Get a quiz."""
        return self._get(f"courses/{course_id}/quizzes/{quiz_id}")

    def get_quiz_questions(self, course_id: int, quiz_id: int) -> list[dict]:
        """Get questions for a quiz."""
        return self._get_paginated(f"courses/{course_id}/quizzes/{quiz_id}/questions")

    # ── Todo ──────────────────────────────────────────────────────────

    def get_todo_items(self) -> list[dict]:
        """Get todo items for the current user."""
        return self._get("users/self/todo")

    # ── Calendar ──────────────────────────────────────────────────────

    def get_calendar_events(self, days: int = 14) -> list[dict]:
        """Get upcoming calendar events."""
        start = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        return self._get_paginated(
            "calendar_events",
            params={"start_date": start, "end_date": end, "type": "event"},
        )

    def get_calendar_assignments(self, days: int = 14) -> list[dict]:
        """Get upcoming assignment due dates from calendar."""
        start = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        return self._get_paginated(
            "calendar_events",
            params={"start_date": start, "end_date": end, "type": "assignment"},
        )
