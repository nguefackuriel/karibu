"""The speech step, run against a real recording.

The fixture is a French sentence spoken by the system voice, so the test needs
no microphone and no network. It is skipped where faster-whisper is not
installed, because the rest of Karibu works without it.
"""

from pathlib import Path

import pytest

from hub.services.listing import read
from hub.services.voice import Whisper

FIXTURE = Path(__file__).parent / "fixtures" / "host-signup-fr.wav"

pytestmark = pytest.mark.skipif(
    not Whisper().available() or not FIXTURE.exists(),
    reason="faster-whisper or the recording is not available on this machine",
)


@pytest.mark.slow
def test_a_real_recording_becomes_a_complete_listing():
    transcript = Whisper(size="small").transcribe(FIXTURE)
    assert "chambre" in transcript.lower()

    got = read(transcript)
    assert got.rooms == 2
    assert got.price_per_night == 8000
    assert got.breakfast is True
    assert got.place and "Bafang" in got.place
    assert got.complete
