"""Turning a host's recording into words.

Whisper runs on the hub's own CPU. There is no speech service and no audio
leaves the machine, which matters because a host is recorded in their own home.
The model is loaded once and kept, since loading it is the slow part.
"""

from __future__ import annotations

import time
from pathlib import Path


class TranscriptionUnavailable(RuntimeError):
    """Raised when no speech recogniser is installed on this hub."""


class Whisper:
    """faster-whisper, int8 on CPU."""

    def __init__(self, size: str = "small", language: str = "fr"):
        self.size = size
        self.language = language
        self._model = None
        self.last_latency: float | None = None

    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise TranscriptionUnavailable(
                    "faster-whisper is not installed on this hub"
                ) from error
            self._model = WhisperModel(self.size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: str | Path) -> str:
        started = time.perf_counter()
        try:
            model = self._load()
            segments, _ = model.transcribe(
                str(audio_path), language=self.language, vad_filter=True
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            self.last_latency = time.perf_counter() - started
        return text
