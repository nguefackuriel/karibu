"""How a message actually leaves the hub.

Two ways out, same interface. The console gateway keeps everything on the
machine, which is what the demo and the tests use. The Africa's Talking gateway
sends a real SMS through their sandbox. Swapping one for the other changes no
code anywhere else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import httpx

SEGMENT = 160


def count_segments(text: str) -> int:
    """How many SMS this text will cost the sender."""
    if len(text) <= SEGMENT:
        return 1
    return -(-len(text) // 153)  # concatenated SMS carry 153 usable characters


@dataclass
class Sent:
    to: str
    text: str
    at: datetime = field(default_factory=datetime.now)
    segments: int = 1
    ok: bool = True
    detail: str = ""


class Gateway:
    name = "abstract"

    def send_sms(self, to: str, text: str) -> Sent:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleGateway(Gateway):
    """Writes the SMS to the terminal and remembers it. No account needed."""

    name = "console"

    def __init__(self, echo: bool = True):
        self.echo = echo
        self.outbox: list[Sent] = []

    def send_sms(self, to: str, text: str) -> Sent:
        sent = Sent(to=to, text=text, segments=count_segments(text))
        self.outbox.append(sent)
        if self.echo:
            print(f"  SMS -> {to}  ({sent.segments} segment, {len(text)} chars)\n    {text}")
        return sent


class AfricasTalkingGateway(Gateway):
    """The sandbox, which sends to the Africa's Talking simulator."""

    name = "africastalking"
    SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
    LIVE_URL = "https://api.africastalking.com/version1/messaging"

    def __init__(self, api_key: str | None = None, username: str = "sandbox",
                 sender: str | None = None, timeout: float = 20.0):
        self.api_key = api_key or os.environ.get("AT_API_KEY", "")
        self.username = username or os.environ.get("AT_USERNAME", "sandbox")
        self.sender = sender or os.environ.get("AT_SENDER") or None
        self.timeout = timeout
        self.outbox: list[Sent] = []

    @property
    def url(self) -> str:
        return self.SANDBOX_URL if self.username == "sandbox" else self.LIVE_URL

    def send_sms(self, to: str, text: str) -> Sent:
        segments = count_segments(text)
        if not self.api_key:
            sent = Sent(to, text, segments=segments, ok=False, detail="AT_API_KEY is not set")
            self.outbox.append(sent)
            return sent

        payload = {"username": self.username, "to": to, "message": text}
        if self.sender:
            payload["from"] = self.sender
        try:
            response = httpx.post(
                self.url,
                data=payload,
                headers={"apiKey": self.api_key, "Accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            recipients = body.get("SMSMessageData", {}).get("Recipients", [])
            ok = bool(recipients) and recipients[0].get("status") == "Success"
            detail = recipients[0].get("status", "") if recipients else str(body)[:200]
        except Exception as error:
            ok, detail = False, str(error)[:200]

        sent = Sent(to, text, segments=segments, ok=ok, detail=detail)
        self.outbox.append(sent)
        return sent


def from_environment() -> Gateway:
    """Use the real sandbox when a key is present, the console otherwise."""
    if os.environ.get("AT_API_KEY"):
        return AfricasTalkingGateway()
    return ConsoleGateway()
