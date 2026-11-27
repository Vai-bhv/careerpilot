import os

import httpx

from app.config import token


class WorkspaceAPI:
    def __init__(self):
        self.base = os.getenv("CAREERPILOT_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/v1"

    def request(self, method, path, **kwargs):
        response = httpx.request(
            method,
            self.base + path,
            headers={"Authorization": "Bearer " + token()},
            timeout=100,
            follow_redirects=False,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def call(self, method, path, **kwargs):
        return self.request(method, path, **kwargs).json()
