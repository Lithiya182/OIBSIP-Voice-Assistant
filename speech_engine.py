import logging
import speech_recognition as sr

logger = logging.getLogger(__name__)

# Sentinel values returned by listen() so the controller can show the right message
LISTEN_NO_SPEECH = ""          # timed out or not understood
LISTEN_HW_ERROR  = "__HW_ERROR__"   # microphone not available


def speak(text: str) -> None:
    """
    Speak text using pyttsx3.

    The engine is created per-call for thread safety. A try/finally block
    ensures engine.stop() is always called, preventing COM resource leaks
    on Windows even if runAndWait() raises.
    """
    engine = None
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logger.error("TTS error: %s", e)
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass


def listen() -> str:
    """
    Listen for a voice command and return the recognised text (lowercase).

    Returns:
        LISTEN_HW_ERROR  — microphone not found / PyAudio not installed
        LISTEN_NO_SPEECH — timed out, speech not understood, or API error
        <text>           — successfully recognised command
    """
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            logger.debug("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.debug("Listening for command...")
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)
    except sr.WaitTimeoutError:
        logger.warning("Listening timed out — no speech detected.")
        return LISTEN_NO_SPEECH
    except OSError as e:
        logger.error("Microphone hardware error: %s", e)
        return LISTEN_HW_ERROR
    except Exception as e:
        # Catches ImportError from missing PyAudio, AttributeError, etc.
        logger.error("Microphone setup error: %s", e)
        return LISTEN_HW_ERROR

    try:
        command = recognizer.recognize_google(audio)
        logger.info("Recognised: %s", command)
        return command.lower()
    except sr.UnknownValueError:
        logger.warning("Speech not understood.")
        return LISTEN_NO_SPEECH
    except sr.RequestError as e:
        logger.error("Google Speech API error: %s", e)
        return LISTEN_NO_SPEECH
