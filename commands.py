import datetime
import webbrowser
import subprocess
import platform
import re
import logging
import urllib.parse
import wikipedia
import requests
from weather import get_weather
from notes import save_note, read_notes, delete_note, clear_notes

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 300
MAX_NOTE_LENGTH = 500
MAX_TOPIC_LENGTH = 100

FILLER_WORDS = {"the", "a", "an", "of", "is", "it", "in", "at", "on", "for"}

_DEFAULT_CITY = "Chennai"

# ── Config loading ────────────────────────────────────────────────────────────

def _load_config() -> dict:
    """Load config.json from the project root, if present."""
    import json
    from pathlib import Path
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning("Could not read config.json: %s", e)
        return {}

_CONFIG = _load_config()
_city_raw = _CONFIG.get("default_city", _DEFAULT_CITY)
# Validate: must be a non-empty string; fall back to built-in default otherwise
DEFAULT_CITY: str = _city_raw if isinstance(_city_raw, str) and _city_raw.strip() else _DEFAULT_CITY


# ── Sanitisation ──────────────────────────────────────────────────────────────

def sanitise(text: str, max_len: int = MAX_INPUT_LENGTH) -> str:
    text = text.strip()[:max_len]
    return re.sub(r"[^\w\s,.'-]", "", text)

def _normalise_times(text: str) -> str:
    """
    Fix speech-recognition time mangling before saving a note.

    STT drops the colon, so "8:00 p.m." arrives as "800 pm" or "800 p.m.".
    Rewrites bare 3-4 digit runs followed by an am/pm marker:
        "800 p.m."  -> "8:00 p.m."
        "1230 pm"   -> "12:30 pm"
    """
    return re.sub(
        r"\b(\d{1,2})(\d{2})\s*(a\.?m\.?|p\.?m\.?)\b",
        lambda m: f"{m.group(1)}:{m.group(2)} {m.group(3)}",
        text,
        flags=re.IGNORECASE,
    )


# ── City extraction (improved: handles "Weather Chennai" without preposition) ─

def extract_city(command: str) -> str:
    # Primary: preposition-based
    match = re.search(r"\b(?:in|at|for)\s+([a-zA-Z\s]+?)(?:\?|$)", command)
    if match:
        city = match.group(1).strip()
        city_words = [w for w in city.split() if w.lower() not in FILLER_WORDS]
        return " ".join(city_words) if city_words else DEFAULT_CITY

    # Fallback: strip known trigger words, use the remainder as the city
    WEATHER_WORDS = {"weather", "temperature", "forecast", "what", "is", "the", "current"}
    remainder = [
        w for w in command.split()
        if w.lower() not in WEATHER_WORDS and w.lower() not in FILLER_WORDS
    ]
    if remainder:
        return " ".join(remainder)

    return DEFAULT_CITY


# ── Command processor ─────────────────────────────────────────────────────────

def process_command(command: str, context: dict | None = None) -> str:
    """
    Process a voice/text command and return a response string.
    `context` is an optional dict maintained by AssistantController for
    follow-up commands (last_topic, last_search, last_city).
    """
    if context is None:
        context = {}

    command = sanitise(command).lower()

    if not command:
        return "I didn't catch that. Please try again."

    # ── Help / capabilities ───────────────────────────────────────────────────
    elif any(w in command for w in [ "what can you do", "what are the tasks", "what are the task","help", "commands", "tasks", "capabilities", "features"]):
        return (
            "Here's what I can do:\n"
            "• Time & date — 'what's the time', 'what's the date'\n"
            "• Weather — 'weather in Mumbai'\n"
            "• Wikipedia — 'tell me about black holes'\n"
            "• Web search — 'search Python tutorials'\n"
            "• Notes — 'take a note buy milk', 'show notes', 'delete note 2', 'clear notes'\n"
            "• Open apps — 'open calculator', 'open notepad', 'open Chrome'\n"
            "• Exit — 'goodbye' or 'exit'\n"
            "Tip: press Ctrl+Shift+Space to activate the microphone."
        )

    # ── Greetings ─────────────────────────────────────────────────────────────
    elif any(word in command for word in ["hello", "hi", "hey"]):
        return "Hello! How can I help you?"

    elif "who are you" in command:
        return "I am Vox, your voice assistant."

    elif "how are you" in command:
        return "I'm doing great, thank you for asking!"

    elif "good boy" in command:
        return "Thank you. I try my best."

    elif "thank you" in command or "thanks" in command:
        return "You are welcome!"

    # ── Date / Time ───────────────────────────────────────────────────────────
    elif "date" in command and "time" in command:
        now = datetime.datetime.now()
        return (
            f"Today is {now.strftime('%d %B %Y')} "
            f"and the time is {now.strftime('%I:%M %p')}."
        )

    elif "time" in command:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The time is {current_time}."

    elif "date" in command:
        current_date = datetime.datetime.now().strftime("%d %B %Y")
        return f"Today is {current_date}."

    # ── Open Applications ─────────────────────────────────────────────────────
    elif "calculator" in command:
        _open_app("calc", "gnome-calculator", "Calculator")
        return "Opening Calculator."

    elif "notepad" in command:
        _open_app("notepad", "gedit", "Notepad")
        return "Opening Notepad."

    elif "paint" in command:
        _open_app("mspaint", "kolourpaint", "Paint")
        return "Opening Paint."

    elif "command prompt" in command or "cmd" in command:
        _open_app("cmd", "x-terminal-emulator", "Terminal")
        return "Opening Terminal."

    elif "file explorer" in command or "explorer" in command:
        _open_app("explorer", "nautilus", "File Explorer")
        return "Opening File Explorer."

    elif "chrome" in command:
        _open_chrome()
        return "Opening Chrome."

    # ── Web ───────────────────────────────────────────────────────────────────
    elif "youtube" in command:
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube."

    elif "search" in command:
        query = sanitise(command.replace("search", "").strip(), 200)
        # Context: follow-up "search that" after a Wikipedia result
        if not query and context.get("last_topic"):
            query = context["last_topic"]
        if not query:
            return "What would you like me to search for?"
        encoded = urllib.parse.urlencode({"q": query})
        webbrowser.open(f"https://www.google.com/search?{encoded}")
        context["last_search"] = query
        return f"Searching for '{query}'."

    # ── Wikipedia ─────────────────────────────────────────────────────────────

    # Pending state: user said "tell me about" with no topic last turn —
    # treat the entire current message as the topic answer.
    elif context.get("_pending_topic"):
        context.pop("_pending_topic")
        topic = sanitise(command, MAX_TOPIC_LENGTH)
        if not topic:
            return "I didn't catch a topic. Try: 'tell me about Python'."
        result = _wikipedia_lookup(topic, sentences=2)
        if result:
            context["last_topic"] = topic
            return result
        return f"Sorry, I couldn't find information about '{topic}'."

    elif "tell me about" in command:
        topic = sanitise(
            command.replace("tell me about", "").strip(),
            MAX_TOPIC_LENGTH
        )
        if not topic:
            context["_pending_topic"] = True
            return "What topic would you like to know about?"
        result = _wikipedia_lookup(topic, sentences=2)
        if result:
            context["last_topic"] = topic
            return result
        return f"Sorry, I couldn't find information about '{topic}'."

    # Bare "tell me" (without "about") — treat same as "tell me about"
    elif re.match(r"^tell me\b", command) and "more" not in command:
        topic = sanitise(
            re.sub(r"^tell me\s*", "", command).strip(),
            MAX_TOPIC_LENGTH
        )
        if not topic:
            context["_pending_topic"] = True
            return "What topic would you like to know about?"
        result = _wikipedia_lookup(topic, sentences=2)
        if result:
            context["last_topic"] = topic
            return result
        return f"Sorry, I couldn't find information about '{topic}'."

    # Context: "tell me more" / "more" / "continue" shortcut
    elif command.strip() in ("tell me more", "more", "continue"):
        if context.get("last_topic"):
            topic = context["last_topic"]
            result = _wikipedia_lookup(topic, sentences=4)
            if result:
                return result
            return f"I couldn't fetch more about '{topic}'."
        return "I'm not sure what to tell you more about. Try 'tell me about <topic>'."

    # ── Weather ───────────────────────────────────────────────────────────────
    elif "weather" in command:
        city = extract_city(command)
        context["last_city"] = city
        return get_weather(city)

    # ── Notes ─────────────────────────────────────────────────────────────────
    elif "take a note" in command:
        note = sanitise(
            command.replace("take a note", "").strip(),
            MAX_NOTE_LENGTH
        )
        if not note:
            return "Please say the note content after 'take a note'."
        note = _normalise_times(note)
        save_note(note)
        return "Note saved successfully."

    elif "show notes" in command or "read notes" in command:
        return read_notes()

    elif re.search(r"\bdelete note\b", command):
        m = re.search(r"delete note\s+(\d+)", command)
        if m:
            idx = int(m.group(1))
            return delete_note(idx)
        return "Please specify which note number to delete, e.g. 'delete note 2'."

    elif "clear all notes" in command or "clear notes" in command:
        return clear_notes()

    # ── Exit ──────────────────────────────────────────────────────────────────
    elif any(word in command for word in ["exit", "goodbye", "bye", "quit"]):
        return "exit"

    else:
        return (
            "Sorry, I didn't understand that. "
            "Try saying 'search', 'time', 'weather', 'tell me about', "
            "'take a note', 'show notes', 'delete note <n>', or 'clear notes'."
        )


# ── App launcher ──────────────────────────────────────────────────────────────

def _open_app(win_cmd: str, linux_cmd: str, name: str) -> None:
    """Launch an app using subprocess (no shell=True, avoids injection)."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run([win_cmd], shell=False, check=False)
        elif system == "Darwin":
            subprocess.run(["open", "-a", name], check=False)
        else:
            subprocess.run([linux_cmd], check=False)
    except FileNotFoundError:
        logger.error("App not found: %s (%s)", name, linux_cmd)
    except Exception as e:
        logger.error("Failed to open %s: %s", name, e)


def _open_chrome() -> None:
    """Cross-platform Chrome launcher."""
    system = platform.system()
    candidates = {
        "Windows": ["chrome", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"],
        "Darwin":  ["open", "-a", "Google Chrome"],
        "Linux":   ["google-chrome", "chromium-browser", "chromium"],
    }
    try:
        if system == "Darwin":
            subprocess.run(candidates["Darwin"], check=False)
        else:
            for cmd in candidates.get(system, []):
                try:
                    subprocess.run([cmd], check=False)
                    return
                except FileNotFoundError:
                    continue
            webbrowser.open("https://www.google.com")
    except Exception as e:
        logger.error("Failed to open Chrome: %s", e)
        webbrowser.open("https://www.google.com")


def _wikipedia_lookup(topic: str, sentences: int = 2) -> str | None:
    """
    Fetch a Wikipedia summary using four progressively looser strategies.

    1. Title-cased, auto_suggest=False  ("Cyber Security")
    2. Collapsed (no spaces), auto_suggest=False  ("Cybersecurity")
    3. auto_suggest=True on original topic  (Wikipedia resolves redirects)
    4. Wikipedia REST /page/summary API via requests — most reliable, bypasses
       the python library entirely and follows redirects server-side.

    DisambiguationErrors are resolved by trying the first suggested option.
    Returns the summary string on success, or None if all four strategies fail.
    """
    # Normalise: strip extra spaces
    topic = " ".join(topic.split())

    # Build candidate title list
    title_candidates = [
        topic.title(),                          # "Cyber Security"
        topic.replace(" ", "").title(),         # "Cybersecurity"
        topic.capitalize(),                     # "cyber security" → "Cyber security"
    ]

    # Strategies 1–2: auto_suggest=False with different title forms
    for title in title_candidates:
        try:
            summary = wikipedia.summary(title, sentences=sentences, auto_suggest=False)
            if summary:
                return _trim_sentences(summary, sentences)
        except wikipedia.DisambiguationError as e:
            # Try each disambiguation option via REST (more reliable than library)
            for option in e.options[:5]:
                result = _wikipedia_rest(option, sentences)
                if result:
                    logger.info("Wikipedia: resolved disambiguation '%s' → '%s'", title, option)
                    return result
        except wikipedia.PageError:
            pass
        except Exception as e:
            logger.error("Wikipedia error on '%s': %s", title, e)

    # Strategy 3: auto_suggest=True (Wikipedia resolves redirects/aliases)
    for title in title_candidates:
        try:
            summary = wikipedia.summary(title, sentences=sentences, auto_suggest=True)
            if summary:
                logger.info("Wikipedia auto_suggest resolved '%s'", title)
                return _trim_sentences(summary, sentences)
        except wikipedia.DisambiguationError as e:
            for option in e.options[:5]:
                result = _wikipedia_rest(option, sentences)
                if result:
                    return result
        except Exception:
            pass

    # Strategy 4: Wikipedia REST API — most reliable, handles redirects natively
    for title in title_candidates:
        result = _wikipedia_rest(title, sentences)
        if result:
            logger.info("Wikipedia REST API resolved '%s'", title)
            return result

    return None


def _wikipedia_rest(title: str, sentences: int = 2) -> str | None:
    """
    Use the Wikipedia REST API /page/summary endpoint.
    This follows redirects server-side (e.g. "Cybersecurity" → "Computer security")
    and is more robust than the python wikipedia library for ambiguous titles.

    Disambiguation pages are detected and skipped (type == "disambiguation").
    """
    try:
        slug = title.replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
        resp = requests.get(url, timeout=6, headers={"User-Agent": "Vox-Assistant/1.0"})
        if resp.status_code == 200:
            data = resp.json()
            # Skip disambiguation pages — their extract starts with "X may refer to:"
            if data.get("type") == "disambiguation":
                logger.debug("Wikipedia REST: '%s' is a disambiguation page, skipping.", title)
                return None
            extract = data.get("extract", "")
            if extract:
                return _trim_sentences(extract, sentences)
        elif resp.status_code == 404:
            pass  # try next candidate
        else:
            logger.warning("Wikipedia REST returned %s for '%s'", resp.status_code, title)
    except Exception as e:
        logger.error("Wikipedia REST error for '%s': %s", title, e)
    return None


def _trim_sentences(text: str, n: int) -> str:
    """Return the first n sentences of text (period-aware, simple split)."""
    import re as _re
    # Split on sentence-ending punctuation followed by space or end-of-string
    sentences = _re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:n])