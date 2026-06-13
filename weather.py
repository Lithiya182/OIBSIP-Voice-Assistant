import logging
import re
import urllib.parse
import requests

logger = logging.getLogger(__name__)

TIMEOUT = 5


def get_weather(city: str) -> str:
    # Sanitise city before embedding in URL (prevents path/query injection)
    safe_city = urllib.parse.quote(city.strip(), safe="")
    url = f"https://wttr.in/{safe_city}?format=3"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        raw = response.text.strip()
        # Strip non-renderable characters (emoji, special Unicode icons)
        # that tkinter's Label widget cannot display
        clean = _strip_non_renderable(raw)
        return clean
    except requests.exceptions.ConnectionError:
        logger.error("No internet connection when fetching weather.")
        return "Unable to fetch weather — please check your internet connection."
    except requests.exceptions.Timeout:
        logger.error("Weather request timed out for city: %s", city)
        return f"Weather request timed out for '{city}'. Try again shortly."
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error fetching weather: %s", e)
        return f"Could not fetch weather for '{city}'."
    except requests.exceptions.RequestException as e:
        logger.error("Weather fetch failed: %s", e)
        return "Unable to fetch weather at this time."


def _strip_non_renderable(text: str) -> str:
    """
    Remove characters outside the Basic Multilingual Plane (emoji, pictographs)
    that tkinter's default font cannot render, while preserving ASCII and
    common Latin/extended characters.
    """
    # Keep only codepoints ≤ U+FFFF (BMP); most emoji are U+1F000–U+1FFFF
    cleaned = "".join(ch for ch in text if ord(ch) <= 0xFFFF)
    # Additionally strip the specific wttr.in icon characters (U+E000–U+F8FF private use area)
    cleaned = re.sub(r"[\uE000-\uF8FF]", "", cleaned)
    return cleaned.strip()
