# Video script

Two minutes fifty. English subtitles. Field tone, not startup tone. Say the
words below more or less as they are written. They are short on purpose, because
you are reading them while things happen on screen.

## Before you press record

Open these and leave them open. Nothing here can be improvised on the day.

1. Start the hub: `uvicorn hub.app:app --port 8000`
2. Start the tunnel: `./scripts/tunnel.sh`, and paste the address it prints into
   the Africa's Talking incoming-messages callback.
3. Open the visitor page at `http://127.0.0.1:8000/visitor`
4. Open the dashboard at `http://127.0.0.1:8000/`
5. Open the Africa's Talking simulator and connect the host's number.
6. Reset the data so the dashboard starts clean: `rm karibu.db && python -m hub.seed`
7. Do one full run to warm the model, then reset again. The first model call is
   slow because it loads, and you do not want that on camera.

Record the screen at 1080p or better. Put the browser at about 80 percent zoom
so the visitor page and the simulator fit side by side.

## The script

| Time | On screen | What you say |
| --- | --- | --- |
| 0:00 | Slide 2, the photo or the name Nathalie | Nathalie rents two rooms in Bafang, a village in Cameroon next to the Metché falls. Visitors walk past her door every week. She has a phone with buttons, no website, and no way to be booked. |
| 0:12 | Same slide | Every booking platform assumes a smartphone, a steady connection and a bank card. She has none of the three, so the money stops with agents in the city. |
| 0:22 | Visitor page, typing in Korean | So we built Karibu. Here is a Korean traveller asking for two nights from the twelfth of October, for two people, with breakfast. |
| 0:32 | The understood panel appearing | Karibu reads the message and shows exactly what it understood. Each line says whether a rule read it or the model did. |
| 0:40 | The simulator, message arriving | And here is what Nathalie gets. One text message, in French, one hundred and six characters, a single SMS segment. |
| 0:50 | Typing 1 in the simulator | She answers with one character. |
| 0:56 | Visitor page showing the Korean confirmation | The traveller is confirmed, in Korean, with the dates, the price and a reference. That whole exchange just went over a real mobile API. |
| 1:06 | Slide 4, the architecture | Everything runs on one machine. A laptop here, a Raspberry Pi in a tourism office. The rules, a one billion parameter model and the speech recognition are all local. No part of taking a booking touches the internet. |
| 1:22 | Terminal, the voice sign-up | Nathalie signed herself up by speaking. She described her rooms out loud, and Karibu turned it into a listing she confirmed with a one. She never typed anything. |
| 1:40 | Slide 5, the two model failures | Here is the decision that shapes the whole system. We tested the small model before trusting it. Asked to read "du 20 au 23 octobre" it answered the twenty third. Asked about a message that never mentioned food, it said breakfast was included, every time. |
| 1:58 | Same slide | So the model never reads a date and never writes a message. Rules read the dates, the nights, the guests and the prices, in three languages. The model only fills what the rules leave blank, and it can never overwrite them. |
| 2:10 | Slide 6, the numbers | The rules answer in a tenth of a millisecond. A completed booking costs about eight cents. A hub for a whole tourism office costs about eighty dollars, once. |
| 2:22 | Slide 7, the trade-offs | Here is what we gave up. The host gets one hundred and sixty characters instead of a screen, and answers with one character. Confirmation is not instant, so the traveller is told to wait up to two hours. And no booking is ever final without a person saying yes. |
| 2:40 | Dashboard | The tourism office sees every room, every booking and the money staying in the village. The catalogue is open, so any destination portal can list these rooms. |
| 2:50 | Slide 8, the ask | We want one tourism office and ten hosts, for one season. |

## What not to do

- Do not say "AI powered" or "leveraging". Say what it does.
- Do not read the numbers table out loud. Two numbers is enough.
- Do not apologise for the trade-offs. Each one is a choice.
- Do not show code. Judges asked for a working thing, not a repository tour.
- Do not let the first forty seconds be slides. The demo has to start early.

## Subtitles

Burn them in or supply an SRT. The judges are not all francophone and the audio
will be compressed. Every number you say must also appear on screen.
