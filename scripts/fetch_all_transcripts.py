#!/usr/bin/env python3
"""
Fetch transcripts for all videos listed in video_ids.txt.

- Tries the existing skill script (fetch_transcript.py) first.
- If that fails, falls back to yt-dlp to download auto‑generated subtitles.
- Saves each transcript as <video_id>.txt in /home/sergio/denaro/video_transcripts.
- Logs activity to /home/sergio/denaro/logs/transcript_fetch.log.
"""

import json, os, sys, time, subprocess, logging, pathlib

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
IDS_PATH = "/home/sergio/denaro/video_ids.txt"
TRAN_DIR = "/home/sergio/denaro/video_transcripts"
LOG_PATH = "/home/sergio/denaro/logs/transcript_fetch.log"

# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------
os.makedirs(TRAN_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

def fetch_via_skill(vid: str) -> str | None:
    """Attempt to fetch transcript using the youtube-content skill script."""
    cmd = [
        "python3",
        "~/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py",
        f"https://www.youtube.com/watch?v={vid}",
        "--text-only",
    ]
    for attempt in range(3):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except Exception:
            pass
        time.sleep(2 ** attempt)  # exponential back‑off
    return None


def fetch_via_yt_dlp(vid: str) -> str | None:
    """Fallback: use yt-dlp to download auto‑generated subtitles."""
    out_path = pathlib.Path(TRAN_DIR) / f"{vid}.txt"
    try:
        cmd = [
            "yt-dlp",
            "--quiet",
            "--no-warnings",
            "--write-auto-sub",
            "--sub-lang",
            "en",
            "--skip-download",
            f"https://www.youtube.com/watch?v={vid}",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            out_path.write_text(result.stdout, encoding="utf-8")
            logging.info("Fetched via yt-dlp: %s", vid)
            return result.stdout
    except Exception as e:
        logging.error("yt-dlp failed for %s: %s", vid, e)
    return None


def main() -> None:
    """Iterate over all video IDs and fetch transcripts."""
    with open(IDS_PATH, "r") as f:
        # Each line is: <index>|<youtube_id>
        ids = [
            line.strip().split("|")[1] for line in f if "|" in line and line.strip()
        ]

    for vid in ids:
        if not vid:
            continue
        logging.info("Attempting fetch for video ID: %s", vid)
        txt = fetch_via_skill(vid)
        if not txt:
            txt = fetch_via_yt_dlp(vid)
        if txt:
            out_path = pathlib.Path(TRAN_DIR) / f"{vid}.txt"
            out_path.write_text(txt, encoding="utf-8")
            logging.info("Saved transcript for %s (%d chars)", vid, len(txt))
        else:
            logging.warning("Failed to fetch transcript for %s", vid)


if __name__ == "__main__":
    main()