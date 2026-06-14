import logging
import threading

from speech_engine import listen, speak, LISTEN_HW_ERROR
from commands import process_command

logger = logging.getLogger(__name__)


class AssistantController:

    def __init__(self, gui):
        self.gui = gui

        # Short conversation context passed to process_command so follow-ups work
        self._context: dict = {}

        # Debounce / busy lock — prevents simultaneous command threads
        self._busy = threading.Lock()

        # Active TTS thread reference so we can cancel it before starting a new one
        self._tts_thread: threading.Thread | None = None

        # Set to True once an exit command is received; blocks further commands
        self._exiting = False

    # ── Public entry points ───────────────────────────────────────────────────

    def start_listening(self):
        if self._exiting:
            logger.debug("Exiting — ignoring listen request.")
            return
        if not self._busy.acquire(blocking=False):
            logger.debug("Already busy — ignoring listen request.")
            return
        self._disable_buttons()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def handle_text_input(self, command: str):
        if self._exiting:
            logger.debug("Exiting — ignoring text input.")
            return
        if not self._busy.acquire(blocking=False):
            logger.debug("Already busy — ignoring text input.")
            return
        self._disable_buttons()
        threading.Thread(
            target=self._process_text, args=(command,), daemon=True
        ).start()

    # ── Private workers ───────────────────────────────────────────────────────

    def _listen_loop(self):
        try:
            self._safe_set_status("🎤 Listening...")

            command = listen()

            if command == LISTEN_HW_ERROR:
                self._safe_set_status("❌ Microphone not found. Check audio settings.")
                return

            if not command:
                self._safe_set_status("❌ Could not hear. Please try again.")
                return

            self._safe_add_message("You", command)
            self._safe_set_status("🧠 Processing...")

            response = process_command(command, context=self._context)
            self._handle_response(response)
        finally:
            self._busy.release()
            self._enable_buttons()

    def _process_text(self, command: str):
        try:
            self._safe_add_message("You", command)
            self._safe_set_status("🧠 Processing...")
            response = process_command(command, context=self._context)
            self._handle_response(response)
        finally:
            self._busy.release()
            self._enable_buttons()

    def _handle_response(self, response: str):
        if response == "exit":
            self._exiting = True
            self._safe_add_message("Vox", "Goodbye! Have a great day.")
            self.gui.root.after(1500, self.gui.root.destroy)
            return

        self._safe_add_message("Vox", response)
        self._safe_set_status("✅ Ready")
        self._speak_async(response)

    # ── TTS helpers ───────────────────────────────────────────────────────────

    def _speak_async(self, text: str):
        """Cancel any in-progress TTS before starting a new one."""
        # Note: pyttsx3 doesn't expose a safe cross-thread stop, but we join
        # with a short timeout so rapid commands don't pile up.
        if self._tts_thread and self._tts_thread.is_alive():
            # We can't hard-stop the thread, but we stop scheduling further ones
            logger.debug("Previous TTS still running — waiting briefly.")
            self._tts_thread.join(timeout=0.5)

        self._tts_thread = threading.Thread(
            target=speak, args=(text,), daemon=True
        )
        self._tts_thread.start()

    # ── Button debounce helpers ───────────────────────────────────────────────

    def _disable_buttons(self):
        self.gui.root.after(0, lambda: self.gui.set_buttons_enabled(False))

    def _enable_buttons(self):
        self.gui.root.after(0, lambda: self.gui.set_buttons_enabled(True))

    # ── Thread-safe GUI helpers ───────────────────────────────────────────────

    def _safe_set_status(self, text: str):
        self.gui.root.after(0, lambda: self.gui.set_status(text))

    def _safe_add_message(self, sender: str, message: str):
        self.gui.root.after(0, lambda: self.gui.add_message(sender, message))
