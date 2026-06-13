import json
import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Always resolve relative to this file's directory — safe regardless of cwd
NOTES_FILE = Path(__file__).parent / "notes.json"


def save_note(note: str) -> None:
    notes = _load_raw()
    entry = {
        "text": note,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    notes.append(entry)
    _write_raw(notes)


def read_notes() -> str:
    notes = _load_raw()
    if not notes:
        return "You have no saved notes."
    lines = []
    for i, n in enumerate(notes, 1):
        ts_raw = n.get("timestamp", "")
        ts = _format_timestamp(ts_raw)
        text = n.get("text", "")
        lines.append(f"{i}. {ts} — {text}")
    return "\n".join(lines)


def delete_note(index: int) -> str:
    """Delete note by 1-based index. Returns a status string."""
    notes = _load_raw()
    if not notes:
        return "You have no saved notes to delete."
    if index < 1 or index > len(notes):
        return f"There is no note number {index}. You have {len(notes)} note(s)."
    removed = notes.pop(index - 1)
    _write_raw(notes)
    preview = removed.get("text", "")[:40]
    return f"Deleted note {index}: \"{preview}\"."


def clear_notes() -> str:
    """Delete all notes."""
    notes = _load_raw()
    if not notes:
        return "There are no notes to clear."
    _write_raw([])
    return f"All {len(notes)} note(s) cleared."


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format_timestamp(ts: str) -> str:
    """Convert ISO timestamp to a spoken-friendly string like '11 June at 2:03 PM'.

    Uses manual lstrip('0') instead of %-d / %-I so the result is identical on
    Windows, macOS, and Linux (those strftime flags are POSIX-only).
    """
    if not ts:
        return "unknown time"
    try:
        dt = datetime.datetime.fromisoformat(ts)
        day  = dt.strftime("%d").lstrip("0")   # "01" → "1", "11" → "11"
        hour = dt.strftime("%I").lstrip("0")   # "02" → "2", "12" → "12"
        return f"{day} {dt.strftime('%B')} at {hour}:{dt.strftime('%M %p')}"
    except Exception:
        return ts


def _load_raw() -> list:
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Could not read notes: %s", e)
        return []


def _write_raw(notes: list) -> None:
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Could not save notes: %s", e)
