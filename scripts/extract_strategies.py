#!/usr/bin/env python3
import pathlib, re, sys, json, datetime

# Directory with transcript files
TRANSDIR = pathlib.Path("/home/sergio/denaro/video_transcripts")
OUT_FILE = pathlib.Path("/home/sergio/denaro/strategies_extracted.md")

# Keywords that usually introduce a strategy / indicator
KEYWORDS = r"\b(?:strategy|indicator|signal|trade|entry|exit|arbitrage|grid|scalping|mean.reversion|breakout|pullback|momentum|recovery)\b"

pattern = re.compile(KEYWORDS, re.IGNORECASE)

entries = []

for txt_path in TRANSDIR.glob("*.txt"):
    vid = txt_path.stem
    with txt_path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            # Try to capture a leading timestamp like 00:01:23,-- > ...
            timestamp_match = re.match(r"(\d{2}:\d{2}:\d{2})", line)
            timestamp = timestamp_match.group(1) if timestamp_match else "??"
            if pattern.search(line):
                entries.append({
                    "video_id": vid,
                    "timestamp": timestamp,
                    "line": line.strip()
                })

# Sort by timestamp (if usable) else keep order
def sort_key(e):
    try:
        h,m,s = map(int, e["timestamp"].split(":"))
        return h*3600 + m*60 + s
    except Exception:
        return 0

entries.sort(key=sort_key)

# Write markdown
with OUT_FILE.open("w", encoding="utf-8") as out:
    out.write("# Extracted Trading Strategies from Michael Ionita Videos\n\n")
    for ent in entries[:200]:  # limit to first 200 snippets
        out.write(f"## Video `{ent['video_id']}`\n")
        out.write(f"**Timestamp:** {ent['timestamp']}\n")
        out.write(f"**Content:** {ent['line']}\n\n")

print(f"Extracted {len(entries)} strategy snippets into {OUT_FILE}")