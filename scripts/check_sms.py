"""Send one real SMS through the Africa's Talking sandbox and say what happened.

Run this once after putting your key in .env. It proves the gateway works
before the demo, so a missing key is never discovered on camera.

    python scripts/check_sms.py            # sends to KARIBU_HOST_PHONE
    python scripts/check_sms.py +2376xxxx  # or to a number you name
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from channels.gateway import AfricasTalkingGateway, count_segments  # noqa: E402
from hub.app import load_env_file                                   # noqa: E402

MESSAGE = ("Karibu: test. Demande 2n 12-14 oct, 2 pers +petit dej. "
           "Total 16000 FCFA. Repondre 1=OUI 2=NON 3=AUTRE DATE")


def main() -> int:
    load_env_file()
    key = os.environ.get("AT_API_KEY", "")
    username = os.environ.get("AT_USERNAME", "sandbox")
    to = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KARIBU_HOST_PHONE", "")

    print(f"username      : {username}")
    print(f"API key       : {'set, ' + str(len(key)) + ' characters' if key else 'MISSING'}")
    print(f"sending to    : {to or 'MISSING'}")
    print(f"message       : {len(MESSAGE)} characters, {count_segments(MESSAGE)} segment\n")

    if not key:
        print("No AT_API_KEY. Copy .env.example to .env and paste your sandbox key.")
        return 1
    if not to:
        print("No recipient. Set KARIBU_HOST_PHONE in .env or pass a number as an argument.")
        return 1

    gateway = AfricasTalkingGateway(api_key=key, username=username)
    print(f"endpoint      : {gateway.url}\n")
    sent = gateway.send_sms(to, MESSAGE)

    if sent.ok:
        print(f"SENT. The operator accepted it: {sent.detail}")
        print("Open https://developers.africastalking.com/simulator, put the same")
        print("number in, and the message should be waiting there.")
        return 0

    print(f"NOT SENT: {sent.detail}")
    print("\nUsual causes: the key belongs to a different app than the username,")
    print("the number is not in +2376... form, or the sandbox simulator has never")
    print("been opened for that number.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
