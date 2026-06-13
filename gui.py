import tkinter as tk
from tkinter import font as tkfont
import datetime
import platform


COLORS = {
    # Palette: #2C3333 (near-black) · #395B64 (teal) · #A5C9CA (light teal) · #E7F6F2 (mint)
    "bg":          "#2C3333",   # near-black — app background
    "panel":       "#323C3C",   # slightly lighter near-black — entry/panel
    "bubble_user": "#395B64",   # teal — user bubble
    "bubble_nova": "#2F4F58",   # deeper teal — Nova bubble
    "accent":      "#A5C9CA",   # light teal — buttons & accents
    "accent_dim":  "#395B64",   # teal — dimmed accent
    "text":        "#E7F6F2",   # mint white — primary text
    "text_dim":    "#A5C9CA",   # light teal — secondary / placeholder
    "border":      "#1E2828",   # darkest — dividers
    "btn_bg":      "#395B64",   # teal — button bg
    "btn_fg":      "#E7F6F2",   # mint — button text
    "btn_hover":   "#A5C9CA",   # light teal on hover
    "btn_speak_bg":"#A5C9CA",
    "status_ok":   "#A5C9CA",
    "status_err":  "#D06060",
    "status_busy": "#C8A850",
    "you_label":   "#A5C9CA",
    "nova_label":  "#E7F6F2",
    "hint":        "#395B64",
}

# Maximum bubble width as a fraction of window width
BUBBLE_MAX_FRACTION = 0.72


class NovaGUI:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Nova — Voice Assistant")
        self.root.geometry("820x680")
        self.root.minsize(600, 520)
        self.root.configure(bg=COLORS["bg"])
        self.root.resizable(True, True)

        self.listen_callback = lambda: None
        self.text_callback = lambda cmd: None

        # Track current canvas width for dynamic bubble wraplength
        self._canvas_width = 600

        self._build_header()
        self._build_chat()
        self._build_status()
        self._build_input_row()
        self._bind_shortcuts()

        self._greet()

    # ── Build sections ────────────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self.root, bg=COLORS["bg"], pady=0)
        header.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(
            header,
            text="◈  NOVA",
            font=("Courier New", 22, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(side="left")

        self.clock_label = tk.Label(
            header,
            text="",
            font=("Courier New", 11),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
        )
        self.clock_label.pack(side="right", padx=4)
        self._tick_clock()

        sep = tk.Frame(self.root, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=24, pady=(12, 0))

    def _build_chat(self):
        self.chat_frame = tk.Frame(self.root, bg=COLORS["bg"])
        self.chat_frame.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        self.canvas = tk.Canvas(
            self.chat_frame,
            bg=COLORS["bg"],
            highlightthickness=0,
            bd=0,
        )

        # Wider, more visible scrollbar
        self.scrollbar = tk.Scrollbar(
            self.chat_frame,
            orient="vertical",
            command=self.canvas.yview,
            troughcolor=COLORS["panel"],
            bg=COLORS["accent_dim"],
            width=10,
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.messages_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.messages_frame, anchor="nw"
        )

        self.messages_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Cross-platform mouse wheel scroll
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)      # Windows / macOS
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)   # Linux scroll up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)   # Linux scroll down

    def _build_status(self):
        status_frame = tk.Frame(self.root, bg=COLORS["bg"])
        status_frame.pack(fill="x", padx=24, pady=(8, 0))

        self.status_dot = tk.Label(
            status_frame,
            text="●",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg=COLORS["status_ok"],
        )
        self.status_dot.pack(side="left")

        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
        )
        self.status_label.pack(side="left", padx=(4, 0))

    def _build_input_row(self):
        sep = tk.Frame(self.root, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=24, pady=(10, 0))

        # Persistent command hint strip
        hint_frame = tk.Frame(self.root, bg=COLORS["bg"])
        hint_frame.pack(fill="x", padx=24, pady=(4, 0))
        tk.Label(
            hint_frame,
            text="try:  weather · time · date · search · tell me about · take a note · show notes",
            font=("Segoe UI", 8),
            bg=COLORS["bg"],
            fg=COLORS["hint"],
        ).pack(side="left")

        bottom = tk.Frame(self.root, bg=COLORS["bg"], pady=12)
        bottom.pack(fill="x", padx=20)

        # Text entry
        entry_frame = tk.Frame(
            bottom,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        entry_frame.pack(side="left", fill="x", expand=True, ipady=4)

        self.text_entry = tk.Entry(
            entry_frame,
            font=("Segoe UI", 11),
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat",
            bd=6,
        )
        self.text_entry.pack(fill="x", expand=True)
        self.text_entry.bind("<Return>", self._on_text_submit)
        self._add_placeholder()

        # Send (secondary action — normal weight)
        self.send_btn = self._make_button(
            bottom, "Send", self._on_text_submit, width=7,
            bg=COLORS["btn_bg"], hover=COLORS["btn_hover"]
        )
        self.send_btn.pack(side="left", padx=(8, 0))

        # Speak (primary action — accent border + slightly wider)
        self.listen_btn = self._make_button(
            bottom, "🎤  Speak", lambda: self.listen_callback(), width=12,
            bg=COLORS["accent"], hover=COLORS["btn_hover"],
            border_color=COLORS["text"]
        )
        self.listen_btn.pack(side="left", padx=(8, 0))

        # Clear chat — muted styling so it doesn't compete with primary actions
        self.clear_btn = self._make_button(
            bottom, "Clear", self._on_clear_chat, width=7,
            bg=COLORS["panel"], hover=COLORS["border"]
        )
        self.clear_btn.config(fg=COLORS["text_dim"])
        self.clear_btn.pack(side="left", padx=(8, 0))

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _make_button(self, parent, text, command, width=10,
                     bg=None, hover=None, border_color=None):
        bg = bg or COLORS["btn_bg"]
        hover = hover or COLORS["btn_hover"]

        kwargs = dict(
            text=text,
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg=COLORS["btn_fg"],
            activebackground=hover,
            activeforeground=COLORS["btn_fg"],
            relief="flat",
            padx=14,
            pady=8,
            width=width,
            cursor="hand2",
            command=command,
            bd=0,
        )
        if border_color:
            kwargs.update(highlightthickness=2, highlightbackground=border_color)

        btn = tk.Button(parent, **kwargs)
        btn.bind("<Enter>", lambda e, b=btn, h=hover: b.config(bg=h) if b["state"] == "normal" else None)
        btn.bind("<Leave>", lambda e, b=btn, c=bg:   b.config(bg=c) if b["state"] == "normal" else None)
        return btn

    def _add_placeholder(self):
        placeholder = "Type a command or press Speak..."
        self.text_entry.insert(0, placeholder)
        self.text_entry.config(fg=COLORS["text_dim"])
        self._placeholder = placeholder

        def on_focus_in(e):
            if self.text_entry.get() == self._placeholder:
                self.text_entry.delete(0, tk.END)
                self.text_entry.config(fg=COLORS["text"])

        def on_focus_out(e):
            if not self.text_entry.get().strip():
                self.text_entry.delete(0, tk.END)
                self.text_entry.insert(0, self._placeholder)
                self.text_entry.config(fg=COLORS["text_dim"])

        self.text_entry.bind("<FocusIn>", on_focus_in)
        self.text_entry.bind("<FocusOut>", on_focus_out)

    def _bind_shortcuts(self):
        # Ctrl+Shift+Space → trigger Speak button
        self.root.bind(
            "<Control-Shift-space>",
            lambda e: self.listen_callback()
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, text: str):
        if "❌" in text or "error" in text.lower():
            dot_color = COLORS["status_err"]
        elif "✅" in text or "Ready" in text:
            dot_color = COLORS["status_ok"]
        else:
            dot_color = COLORS["status_busy"]

        self.status_dot.config(fg=dot_color)
        clean = (
            text.replace("🎤", "").replace("🧠", "")
                .replace("✅", "").replace("❌", "").strip()
        )
        self.status_label.config(text=clean)

    def set_buttons_enabled(self, enabled: bool):
        """Enable or disable Send/Speak/Clear during processing (debounce)."""
        state = "normal" if enabled else "disabled"
        self.send_btn.config(state=state)
        self.listen_btn.config(state=state)
        self.clear_btn.config(state=state)

    def set_listen_callback(self, callback):
        self.listen_callback = callback

    def set_text_callback(self, callback):
        self.text_callback = callback

    def add_message(self, sender: str, message: str):
        is_user = sender.lower() == "you"
        self._add_bubble(sender, message, is_user)
        self.root.after(50, lambda: self.canvas.yview_moveto(1.0))

    def run(self):
        self.root.mainloop()

    # ── Message bubbles ───────────────────────────────────────────────────────

    def _add_bubble(self, sender: str, message: str, is_user: bool):
        # Tighter vertical padding (was 4 → now 1)
        outer = tk.Frame(self.messages_frame, bg=COLORS["bg"], pady=1)
        outer.pack(fill="x", padx=12)

        bubble_color = COLORS["bubble_user"] if is_user else COLORS["bubble_nova"]
        label_color  = COLORS["you_label"]   if is_user else COLORS["nova_label"]
        side         = "right"               if is_user else "left"
        anchor       = "e"                   if is_user else "w"

        # Dynamic wraplength: fraction of current canvas width
        wrap = max(200, int(self._canvas_width * BUBBLE_MAX_FRACTION))

        bubble = tk.Frame(
            outer,
            bg=bubble_color,
            padx=14,
            pady=8,
        )
        bubble.pack(side=side, anchor=anchor)

        # Sentence-case sender label with better contrast
        tk.Label(
            bubble,
            text=sender.capitalize(),
            font=("Courier New", 8, "bold"),
            bg=bubble_color,
            fg=label_color,
        ).pack(anchor="w")

        tk.Label(
            bubble,
            text=message,
            font=("Segoe UI", 11),
            bg=bubble_color,
            fg=COLORS["text"],
            wraplength=wrap,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

        # Store label reference so we can update wraplength on resize
        # (store all bubble labels for later rescaling)
        if not hasattr(self, "_bubble_labels"):
            self._bubble_labels = []
        self._bubble_labels.append(
            bubble.winfo_children()[-1]  # the message Label
        )

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_clear_chat(self):
        """Destroy all chat bubbles and re-show the greeting."""
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        self._bubble_labels = []
        self.canvas.yview_moveto(0.0)
        self.add_message("Nova", "Chat cleared. How can I help you?")

    def _on_text_submit(self, event=None):
        raw = self.text_entry.get()
        text = raw.strip()
        # Reject empty string AND the placeholder (handles trailing-space edge case)
        if not text or text == self._placeholder:
            return
        self.text_entry.delete(0, tk.END)
        self.text_callback(text)

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        self._canvas_width = event.width
        # Rescale existing bubble labels
        new_wrap = max(200, int(event.width * BUBBLE_MAX_FRACTION))
        for lbl in getattr(self, "_bubble_labels", []):
            try:
                lbl.config(wraplength=new_wrap)
            except tk.TclError:
                pass  # widget was destroyed

    def _on_mousewheel(self, event):
        """Windows: event.delta is ±120 multiples. macOS: event.delta is ±1."""
        if platform.system() == "Darwin":
            self.canvas.yview_scroll(int(-1 * event.delta), "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        """Linux uses Button-4 (scroll up) and Button-5 (scroll down)."""
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _tick_clock(self):
        now = datetime.datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M"))
        # Schedule next tick at the next full minute boundary
        delay = (60 - now.second) * 1000
        self.root.after(delay, self._tick_clock)

    def _greet(self):
        self.add_message("Nova", "Hello! I'm Nova. Speak or type a command to get started.")