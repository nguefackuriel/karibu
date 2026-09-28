"""A very small client for the local model runner.

Karibu talks to one process on the same machine. There is no API key, no
account and no traffic leaving the hub, which is the whole point: the model
must keep working when the internet does not.
"""

from __future__ import annotations

import json
import time

import httpx

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:1b"


class ModelUnavailable(RuntimeError):
    """Raised when the local model runner cannot be reached."""


class Ollama:
    def __init__(self, host: str = DEFAULT_HOST, model: str = DEFAULT_MODEL, timeout: float = 60.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.last_latency: float | None = None

    def available(self) -> bool:
        try:
            httpx.get(f"{self.host}/api/tags", timeout=2.0).raise_for_status()
            return True
        except Exception:
            return False

    def generate_json(self, prompt: str) -> dict:
        """Ask for JSON and return it parsed. Raises ModelUnavailable on failure."""
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()["response"]
        except Exception as error:  # network, timeout, bad status
            raise ModelUnavailable(str(error)) from error
        finally:
            self.last_latency = time.perf_counter() - started

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as error:
            raise ModelUnavailable(f"model did not return JSON: {body[:200]}") from error
        return parsed if isinstance(parsed, dict) else {}
