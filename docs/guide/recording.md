# Recording sessions

**Optional, and only with your table's OK.** Record the session at the table, turn the recording into a transcript on your own computer, and use it to write the Session Log. Nothing is uploaded anywhere.

## Set up

1. Run setup with transcription: `setup.bat --with-transcribe` (Windows, from a terminal) or `./setup.sh --with-transcribe`. It's a large download; the speech model itself (about 1.6 GB) downloads the first time you transcribe.
2. Install **ffmpeg** (<https://ffmpeg.org>; on Windows `winget install ffmpeg`, on macOS `brew install ffmpeg`). Recordings made in the browser need it to be readable.

## Record

With `CampaignCodex5e` running, open the **[Record & Transcribe](../recording.md)** tab in Chrome or Edge:

- Pick the microphone and check the level meter. A USB conference or podcast mic in the middle of the table, set to pick up all around, works best.
- **⧉ Pop out** moves the recorder into a small window of its own, so you can use the rest of the site; a **● REC** light shows on every page while it records.
- The audio is saved every few seconds, so a crash or a closed tab loses seconds, not the session.
- Recordings go in the `recordings/` folder in your campaign (or wherever **Browse…** points). It's never built, published, or committed.

## Transcribe

Press **Transcribe** next to a recording on the same page, or run `transcribe` (Windows: drag a recording onto `transcribe.bat`). It writes `<recording>.transcript.txt` next to the recording, one line per stretch of speech with its time.

It's given your campaign's names first — the party, the people and places of the town in `campaign.yml`'s `focus:`, factions, items — so it spells them right instead of guessing. If the initiative tracker ran a fight during the recording, its turn log is woven into the transcript.

## Write it up

Read the transcript and write the Session Log entry — or ask an AI assistant to draft it (see [Working with an AI assistant](ai-assistant.md)), then edit it yourself.

## Afterward

Transcripts are raw table talk. Keep them private, and **delete the recording and transcript once the Session Log entry is written**, unless everyone at the table is happy to keep them.
