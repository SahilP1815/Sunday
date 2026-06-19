"""
Sunday Desktop App — Main UI
Sleek dark themed customtkinter window with orb, chat log, voice controls.
"""

import threading
import time
import json
import os
import math
import tkinter as tk
from tkinter import font as tkfont
import customtkinter as ctk
from pathlib import Path

from sunday_brain import SundayBrain
from voice_engine import VoiceEngine

# ── Config path ───────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "config.json"

# ── Theme ─────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg":           "#04060f",
    "panel":        "#090d1e",
    "panel_border": "#141a35",
    "orb_idle":     "#1a4fff",
    "orb_listen":   "#ff3d6e",
    "orb_think":    "#00e096",
    "orb_speak":    "#00cfff",
    "text_primary": "#c8e6ff",
    "text_dim":     "#4a6a9a",
    "text_user":    "#78c8ff",
    "text_sunday":  "#a0f0c0",
    "accent":       "#1e50b4",
    "input_bg":     "#080d20",
    "btn_bg":       "#0f1e44",
    "btn_hover":    "#162850",
}

ORB_STATES = {
    "idle":     {"color": COLORS["orb_idle"],   "glow": "#0a2080", "pulse": False},
    "listening":{"color": COLORS["orb_listen"],  "glow": "#400020", "pulse": True},
    "thinking": {"color": COLORS["orb_think"],   "glow": "#003830", "pulse": True},
    "speaking": {"color": COLORS["orb_speak"],   "glow": "#003050", "pulse": True},
}


class SundayApp:
    def __init__(self):
        self.brain = SundayBrain()
        self.config = self._load_config()

        # Apply saved API key
        saved_key = self.config.get("gemini_api_key", "")
        if saved_key:
            self.brain.set_api_key(saved_key)

        self.voice = VoiceEngine(
            on_wake=self._on_wake,
            on_transcript=self._on_transcript,
            on_error=self._on_voice_error,
            on_interim=self._on_interim,
        )
        self._apply_voice_config()

        self.continuous_active = False
        self._orb_state = "idle"
        self._orb_angle = 0
        self._orb_pulse = 1.0
        self._pulse_dir = 1
        self._animating = True

        self._build_ui()

    # ── Config ────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except Exception:
                pass
        return {}

    def _save_config(self, data: dict):
        self.config.update(data)
        CONFIG_FILE.write_text(json.dumps(self.config, indent=2))

    # ── UI Build ──────────────────────────────────────────────────

    def _build_ui(self):
        self.root = ctk.CTk()
        self.root.title("Sunday · AI Assistant")
        self.root.geometry("820x680")
        self.root.minsize(700, 560)
        self.root.configure(fg_color=COLORS["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set window icon
        try:
            icon_path = Path(__file__).parent / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        self._build_header()
        self._build_orb_panel()
        self._build_chat_panel()
        self._build_input_bar()
        self._build_status_bar()

        # Start animations and voice
        self._animate_orb()
        self._start_voice()

        # Keyboard shortcuts
        self.root.bind("<Control-space>", lambda e: self._on_mic_click())

        # Initial greeting
        self.root.after(800, self._greet)

    # ── Header ────────────────────────────────────────────────────

    def _build_header(self):
        hdr = ctk.CTkFrame(self.root, fg_color=COLORS["panel"],
                           corner_radius=0, height=52)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        title = ctk.CTkLabel(
            hdr, text="S U N D A Y",
            font=ctk.CTkFont(family="Courier New", size=16, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        title.pack(side="left", padx=20)

        sub = ctk.CTkLabel(
            hdr, text="· AI ASSISTANT",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=COLORS["text_dim"],
        )
        sub.pack(side="left", padx=0)

        # Settings button
        settings_btn = ctk.CTkButton(
            hdr, text="⚙", width=36, height=30,
            fg_color=COLORS["btn_bg"], hover_color=COLORS["btn_hover"],
            font=ctk.CTkFont(size=16), corner_radius=8,
            command=self._open_settings,
        )
        settings_btn.pack(side="right", padx=12, pady=10)

        # Clear chat
        clear_btn = ctk.CTkButton(
            hdr, text="↺", width=36, height=30,
            fg_color=COLORS["btn_bg"], hover_color=COLORS["btn_hover"],
            font=ctk.CTkFont(size=16), corner_radius=8,
            command=self._clear_chat,
        )
        clear_btn.pack(side="right", padx=4, pady=10)

    # ── Orb panel ─────────────────────────────────────────────────

    def _build_orb_panel(self):
        panel = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], height=200)
        panel.pack(fill="x", padx=0, pady=0)
        panel.pack_propagate(False)

        self.orb_canvas = tk.Canvas(
            panel, width=200, height=200,
            bg=COLORS["bg"], highlightthickness=0,
        )
        self.orb_canvas.pack(side="left", padx=30)
        self.orb_canvas.bind("<Button-1>", lambda e: self._on_mic_click())

        # Right side: status label + quick-action hints
        info_frame = ctk.CTkFrame(panel, fg_color=COLORS["bg"])
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=20)

        self.status_label = ctk.CTkLabel(
            info_frame, text="Initialising...",
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color=COLORS["text_dim"],
        )
        self.status_label.pack(anchor="w", pady=(10, 6))

        self.state_label = ctk.CTkLabel(
            info_frame, text="",
            font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
            text_color=COLORS["orb_idle"],
        )
        self.state_label.pack(anchor="w")

        # Hint chips
        hints = [
            "🎤  Say 'Hey Sunday' to wake",
            "📂  'Open my Downloads folder'",
            "💻  'Launch VS Code'",
            "📊  'Show CPU usage' / 'system status'",
            "🛑  'Close Chrome' / 'Kill Notepad'",
            "⌨   Ctrl + Space to listen",
        ]
        for h in hints:
            chip = ctk.CTkLabel(
                info_frame, text=h,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_dim"],
            )
            chip.pack(anchor="w", pady=1)

    # ── Chat panel ────────────────────────────────────────────────

    def _build_chat_panel(self):
        outer = ctk.CTkFrame(
            self.root, fg_color=COLORS["panel"],
            corner_radius=12,
            border_width=1, border_color=COLORS["panel_border"],
        )
        outer.pack(fill="both", expand=True, padx=16, pady=6)

        self.chat_box = tk.Text(
            outer,
            bg=COLORS["panel"], fg=COLORS["text_primary"],
            font=("Segoe UI", 12), wrap="word",
            state="disabled", relief="flat", bd=0,
            padx=16, pady=12,
            selectbackground=COLORS["accent"],
            insertbackground=COLORS["text_primary"],
        )
        self.chat_box.pack(fill="both", expand=True, padx=2, pady=2)

        scrollbar = ctk.CTkScrollbar(outer, command=self.chat_box.yview)
        scrollbar.place(relx=1, rely=0, relheight=1, anchor="ne")
        self.chat_box.configure(yscrollcommand=scrollbar.set)

        # Define text tags
        self.chat_box.tag_configure("you",    foreground=COLORS["text_user"],    font=("Segoe UI", 11, "bold"))
        self.chat_box.tag_configure("sunday", foreground=COLORS["text_sunday"],  font=("Segoe UI", 11, "bold"))
        self.chat_box.tag_configure("msg",    foreground=COLORS["text_primary"],  font=("Segoe UI", 12))
        self.chat_box.tag_configure("dim",    foreground=COLORS["text_dim"],      font=("Segoe UI", 10, "italic"))
        self.chat_box.tag_configure("error",  foreground="#ff6060",               font=("Segoe UI", 11, "italic"))

    # ── Live transcript banner ────────────────────────────────────

    def _build_input_bar(self):
        # Live transcript (shown while speaking to mic)
        self.live_label = ctk.CTkLabel(
            self.root,
            text="",
            font=ctk.CTkFont(family="Courier New", size=11, slant="italic"),
            text_color=COLORS["orb_listen"],
            anchor="w",
        )
        self.live_label.pack(fill="x", padx=24, pady=(0, 2))

        bar = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], height=60)
        bar.pack(fill="x", padx=16, pady=(4, 8))
        bar.pack_propagate(False)

        self.mic_btn = ctk.CTkButton(
            bar, text="🎤", width=48, height=44,
            fg_color=COLORS["btn_bg"], hover_color="#3a1030",
            font=ctk.CTkFont(size=20), corner_radius=10,
            command=self._on_mic_click,
        )
        self.mic_btn.pack(side="left", padx=(0, 10))

        self.text_input = ctk.CTkEntry(
            bar,
            placeholder_text="Ask Sunday anything or give a command...",
            fg_color=COLORS["input_bg"],
            border_color=COLORS["panel_border"],
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_dim"],
            font=ctk.CTkFont(size=13),
            height=44, corner_radius=10,
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.text_input.bind("<Return>", lambda e: self._on_send())

        self.send_btn = ctk.CTkButton(
            bar, text="Send", width=80, height=44,
            fg_color=COLORS["accent"], hover_color="#2860d0",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            corner_radius=10,
            command=self._on_send,
        )
        self.send_btn.pack(side="left")

    # ── Status bar ────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self.root, fg_color=COLORS["panel"],
                           corner_radius=0, height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_bar_label = ctk.CTkLabel(
            bar, text="Sunday v2.0 · Powered by Gemini",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=COLORS["text_dim"],
        )
        self.status_bar_label.pack(side="right", padx=12)

        self.mic_status = ctk.CTkLabel(
            bar, text="● MICROPHONE IDLE",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=COLORS["text_dim"],
        )
        self.mic_status.pack(side="left", padx=12)

    # ── Orb Animation ─────────────────────────────────────────────

    def _animate_orb(self):
        if not self._animating:
            return

        state  = ORB_STATES[self._orb_state]
        cx, cy = 100, 100
        base_r = 60

        # Pulse effect
        if state["pulse"]:
            self._orb_pulse += 0.04 * self._pulse_dir
            if self._orb_pulse > 1.12 or self._orb_pulse < 0.88:
                self._pulse_dir *= -1
        else:
            self._orb_pulse = 1.0

        r = base_r * self._orb_pulse
        self._orb_angle = (self._orb_angle + 1.2) % 360

        self.orb_canvas.delete("all")

        # Outer glow rings
        for i, (ring_r, alpha) in enumerate([(r+30, 0.07), (r+18, 0.12), (r+8, 0.20)]):
            self.orb_canvas.create_oval(
                cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                outline=state["glow"], width=1 if i == 0 else 2,
            )

        # Rotating orbit dot
        rad = math.radians(self._orb_angle)
        dot_x = cx + (r + 14) * math.cos(rad)
        dot_y = cy + (r + 14) * math.sin(rad)
        self.orb_canvas.create_oval(dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3,
                                    fill=state["color"], outline="")

        # Reverse orbit dot
        rad2 = math.radians(self._orb_angle + 180)
        dot_x2 = cx + (r + 14) * math.cos(rad2)
        dot_y2 = cy + (r + 14) * math.sin(rad2)
        self.orb_canvas.create_oval(dot_x2 - 2, dot_y2 - 2, dot_x2 + 2, dot_y2 + 2,
                                    fill=state["glow"], outline="")

        # Main orb body (gradient simulation via concentric circles)
        steps = 12
        for i in range(steps, 0, -1):
            frac  = i / steps
            cr    = r * frac
            shade = self._blend_color(state["glow"], state["color"], frac * 0.9)
            self.orb_canvas.create_oval(
                cx - cr, cy - cr, cx + cr, cy + cr,
                fill=shade, outline="",
            )

        # Highlight glare
        self.orb_canvas.create_oval(
            cx - r * 0.45, cy - r * 0.5,
            cx + r * 0.1,  cy - r * 0.05,
            fill="white", outline="", stipple="gray25",
        )

        self.root.after(30, self._animate_orb)

    def _blend_color(self, c1: str, c2: str, t: float) -> str:
        """Blend two hex colors by factor t (0=c1, 1=c2)."""
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _set_orb_state(self, state: str):
        """Update orb color state and labels."""
        self._orb_state = state
        labels = {
            "idle":      ("ONLINE · READY",      COLORS["orb_idle"]),
            "listening": ("LISTENING...",         COLORS["orb_listen"]),
            "thinking":  ("PROCESSING...",        COLORS["orb_think"]),
            "speaking":  ("SPEAKING...",          COLORS["orb_speak"]),
        }
        text, color = labels.get(state, ("...", COLORS["text_dim"]))
        self.state_label.configure(text=text, text_color=color)

        mic_texts = {
            "idle":      ("● MICROPHONE IDLE",    COLORS["text_dim"]),
            "listening": ("● LISTENING",          COLORS["orb_listen"]),
            "thinking":  ("● PROCESSING",         COLORS["orb_think"]),
            "speaking":  ("● SPEAKING",           COLORS["orb_speak"]),
        }
        mt, mc = mic_texts.get(state, ("● IDLE", COLORS["text_dim"]))
        self.mic_status.configure(text=mt, text_color=mc)

    # ── Chat helpers ─────────────────────────────────────────────

    def _append_chat(self, speaker: str, message: str, tag: str = "msg"):
        def _write():
            self.chat_box.configure(state="normal")
            timestamp = time.strftime("%H:%M")
            if speaker == "You":
                self.chat_box.insert("end", f"\n[{timestamp}] ", "dim")
                self.chat_box.insert("end", "You\n", "you")
            elif speaker == "Sunday":
                self.chat_box.insert("end", f"\n[{timestamp}] ", "dim")
                self.chat_box.insert("end", "Sunday\n", "sunday")
            self.chat_box.insert("end", f"{message}\n", tag)
            self.chat_box.configure(state="disabled")
            self.chat_box.see("end")
        self.root.after(0, _write)

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_label.configure(text=text))

    # ── Voice callbacks ──────────────────────────────────────────

    def _on_wake(self, wake_text: str):
        """Called when wake word is detected — show in chat UI."""
        self.continuous_active = True
        def _show():
            self._set_orb_state("listening")
            self._set_status(f"Heard wake word — listening for command...")
            # Show a dim system note in chat
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", f"\n🎤 Wake word detected: '{wake_text}'\n", "dim")
            self.chat_box.configure(state="disabled")
            self.chat_box.see("end")
        self.root.after(0, _show)

    def _on_interim(self, partial: str):
        """Called with live partial transcripts — show in live label."""
        def _update():
            if partial:
                self.live_label.configure(text=f"  🎙 {partial}...")
            else:
                self.live_label.configure(text="")
        self.root.after(0, _update)

    def _on_transcript(self, text: str):
        """Called with a recognized voice command."""
        self.root.after(0, lambda: self.live_label.configure(text=""))  # clear live label
        self._append_chat("You", f"🎤  {text}")
        
        # Deactivate continuous mode if a stop/goodbye phrase is said
        stop_phrases = ["stop", "exit", "quit", "goodbye", "go to sleep", "thank you", "that's all", "bye"]
        text_lower = text.lower().strip()
        text_clean = "".join(c for c in text_lower if c.isalnum() or c.isspace())
        should_stop = False
        for phrase in stop_phrases:
            if f" {phrase} " in f" {text_clean} " or text_clean == phrase:
                should_stop = True
                break
        if should_stop:
            self.continuous_active = False
            
        self.root.after(0, lambda: self._set_orb_state("thinking"))
        self.root.after(0, lambda: self._set_status("Thinking..."))
        threading.Thread(target=self._process_message, args=(text,), daemon=True).start()

    def _on_voice_error(self, error: str):
        """Called on voice/mic errors."""
        self.continuous_active = False
        self.root.after(0, lambda: self.live_label.configure(text=""))
        self.root.after(0, lambda: self._set_orb_state("idle"))
        self.root.after(0, lambda: self._set_status(f"⚠ {error}"))

    # ── Input handlers ────────────────────────────────────────────

    def _on_send(self):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, "end")
        self.continuous_active = False
        self._append_chat("You", text)
        self._set_orb_state("thinking")
        self._set_status("Thinking...")
        threading.Thread(target=self._process_message, args=(text,), daemon=True).start()

    def _on_mic_click(self):
        """Manual mic button press — one-shot listen."""
        if self._orb_state == "listening":
            return
        self.continuous_active = True
        self._set_orb_state("listening")
        self._set_status("Listening — speak now...")
        self.voice.listen_once()

    # ── Core processing ───────────────────────────────────────────

    def _process_message(self, text: str):
        """Run AI/system command processing in background thread."""
        reply = self.brain.think(text)
        self._append_chat("Sunday", reply)
        self.root.after(0, lambda: self._set_orb_state("speaking"))
        self.root.after(0, lambda: self._set_status("Speaking..."))
        self.voice.speak(reply)
        # Wait for speech to finish, then return to idle
        threading.Thread(target=self._wait_idle, daemon=True).start()

    def _wait_idle(self):
        """Wait for TTS queue to empty, then set idle."""
        self.voice._tts_queue.join()
        time.sleep(0.3)
        if self.continuous_active:
            self.root.after(0, lambda: self._set_orb_state("listening"))
            self.root.after(0, lambda: self._set_status("Listening — speak now..."))
            self.root.after(0, self.voice.listen_once)
        else:
            self.root.after(0, lambda: self._set_orb_state("idle"))
            self.root.after(0, lambda: self._set_status("Say 'Hey Sunday' or click 🎤"))

    # ── Greeting ──────────────────────────────────────────────────

    def _greet(self):
        greeting = "Sunday online. All systems operational. How may I assist you today?"
        self._append_chat("Sunday", greeting)
        self._set_orb_state("speaking")
        self._set_status("Speaking...")
        self.voice.speak(greeting)
        threading.Thread(target=self._wait_idle, daemon=True).start()

    # ── Start voice ───────────────────────────────────────────────

    def _start_voice(self):
        self._set_status("Starting microphone...")
        threading.Thread(target=self._init_voice_async, daemon=True).start()

    def _init_voice_async(self):
        wake_enabled = self.config.get("wake_word_enabled", True)
        if not wake_enabled:
            self.root.after(0, lambda: self._set_status("Click 🎤 or type command"))
            return
        try:
            self.voice.start_wake_word_listening()
            self.root.after(0, lambda: self._set_status("Say 'Hey Sunday' or click 🎤"))
        except Exception as e:
            self.root.after(0, lambda: self._set_status(f"Mic error: {e}"))

    # ── Settings window ───────────────────────────────────────────

    def _apply_voice_config(self):
        # 1. Microphone device
        mic_idx = self.config.get("mic_device_index", None)
        old_mic_idx = self.voice.device_index
        if mic_idx is not None:
            self.voice.device_index = int(mic_idx)
        else:
            self.voice.device_index = None

        if old_mic_idx != self.voice.device_index:
            self.voice.reset_calibration()

        # 2. Dynamic threshold
        dynamic = self.config.get("dynamic_energy_threshold", True)
        self.voice.recognizer.dynamic_energy_threshold = dynamic

        # 3. Energy threshold
        threshold = self.config.get("energy_threshold", 300)
        self.voice.recognizer.energy_threshold = threshold

        # 4. Wake word enabled
        wake = self.config.get("wake_word_enabled", True)
        self.voice.wake_word_enabled = wake

        # 5. Language configuration
        lang = self.config.get("recognition_language", "en-US")
        self.voice.language = lang

        # 6. Sarvam API Key
        sarvam_key = self.config.get("sarvam_api_key", "")
        self.voice.sarvam_api_key = sarvam_key

    def _open_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Settings")
        win.geometry("520x680")
        win.configure(fg_color=COLORS["panel"])
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(
            win, text="SETTINGS",
            font=ctk.CTkFont(family="Courier New", size=14, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 6))

        # Gemini API Key Section
        api_frame = ctk.CTkFrame(win, fg_color="transparent")
        api_frame.pack(fill="x", padx=24, pady=4)
        
        ctk.CTkLabel(
            api_frame, text="Gemini API Key",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        key_entry = ctk.CTkEntry(
            api_frame, width=472, height=36,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["panel_border"],
            text_color=COLORS["text_primary"],
            show="*",
            font=ctk.CTkFont(size=11),
        )
        key_entry.pack(fill="x", pady=(4, 0))
        if self.config.get("gemini_api_key"):
            key_entry.insert(0, self.config["gemini_api_key"])

        # Sarvam AI API Key Section
        sarvam_frame = ctk.CTkFrame(win, fg_color="transparent")
        sarvam_frame.pack(fill="x", padx=24, pady=4)
        
        ctk.CTkLabel(
            sarvam_frame, text="Sarvam AI API Key (for speech enhancements)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        sarvam_key_entry = ctk.CTkEntry(
            sarvam_frame, width=472, height=36,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["panel_border"],
            text_color=COLORS["text_primary"],
            show="*",
            font=ctk.CTkFont(size=11),
        )
        sarvam_key_entry.pack(fill="x", pady=(4, 0))
        if self.config.get("sarvam_api_key"):
            sarvam_key_entry.insert(0, self.config["sarvam_api_key"])

        # GNews API Key Section
        gnews_frame = ctk.CTkFrame(win, fg_color="transparent")
        gnews_frame.pack(fill="x", padx=24, pady=4)
        
        ctk.CTkLabel(
            gnews_frame, text="GNews API Key (for news updates)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        gnews_key_entry = ctk.CTkEntry(
            gnews_frame, width=472, height=36,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["panel_border"],
            text_color=COLORS["text_primary"],
            show="*",
            font=ctk.CTkFont(size=11),
        )
        gnews_key_entry.pack(fill="x", pady=(4, 0))
        if self.config.get("gnews_api_key"):
            gnews_key_entry.insert(0, self.config["gnews_api_key"])


        # Mic Device Section
        mic_frame = ctk.CTkFrame(win, fg_color="transparent")
        mic_frame.pack(fill="x", padx=24, pady=8)

        ctk.CTkLabel(
            mic_frame, text="Microphone Input Device",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        import speech_recognition as sr
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            names = []

        mic_options = ["Default Microphone"]
        mic_map = {}
        for idx, name in enumerate(names):
            display_name = f"[{idx}] {name}"
            if len(display_name) > 65:
                display_name = display_name[:62] + "..."
            mic_options.append(display_name)
            mic_map[display_name] = idx

        saved_mic_idx = self.config.get("mic_device_index", None)
        selected_option = "Default Microphone"
        if saved_mic_idx is not None:
            for option, idx in mic_map.items():
                if idx == saved_mic_idx:
                    selected_option = option
                    break

        mic_dropdown = ctk.CTkOptionMenu(
            mic_frame,
            values=mic_options,
            width=472,
            height=36,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["btn_bg"],
            button_hover_color=COLORS["btn_hover"],
            dropdown_fg_color=COLORS["panel"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["btn_hover"],
            text_color=COLORS["text_primary"],
        )
        mic_dropdown.pack(fill="x", pady=(4, 0))
        mic_dropdown.set(selected_option)

        # Recognition Language Section
        lang_frame = ctk.CTkFrame(win, fg_color="transparent")
        lang_frame.pack(fill="x", padx=24, pady=8)

        ctk.CTkLabel(
            lang_frame, text="Speech Recognition Language",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        lang_options = {
            "English (United States) [en-US]": "en-US",
            "English (India) [en-IN]": "en-IN",
            "English (United Kingdom) [en-GB]": "en-GB",
            "Hindi (India) [hi-IN]": "hi-IN",
        }

        saved_lang = self.config.get("recognition_language", "en-US")
        selected_lang_opt = "English (United States) [en-US]"
        for opt, val in lang_options.items():
            if val == saved_lang:
                selected_lang_opt = opt
                break

        lang_dropdown = ctk.CTkOptionMenu(
            lang_frame,
            values=list(lang_options.keys()),
            width=472,
            height=36,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["btn_bg"],
            button_hover_color=COLORS["btn_hover"],
            dropdown_fg_color=COLORS["panel"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["btn_hover"],
            text_color=COLORS["text_primary"],
        )
        lang_dropdown.pack(fill="x", pady=(4, 0))
        lang_dropdown.set(selected_lang_opt)

        # Voice Options Section
        voice_frame = ctk.CTkFrame(win, fg_color="transparent")
        voice_frame.pack(fill="x", padx=24, pady=8)

        ctk.CTkLabel(
            voice_frame, text="Voice & Listening Preferences",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, 6))

        # Checkboxes
        wake_var = tk.BooleanVar(value=self.config.get("wake_word_enabled", True))
        wake_cb = ctk.CTkCheckBox(
            voice_frame, text="Continuous 'Hey Sunday' wake-word listening",
            variable=wake_var,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["btn_hover"],
        )
        wake_cb.pack(anchor="w", pady=4)

        dynamic_var = tk.BooleanVar(value=self.config.get("dynamic_energy_threshold", True))
        dynamic_cb = ctk.CTkCheckBox(
            voice_frame, text="Dynamic background noise threshold adjustment",
            variable=dynamic_var,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["btn_hover"],
            command=lambda: toggle_thresh_state()
        )
        dynamic_cb.pack(anchor="w", pady=4)

        # Manual threshold setting
        thresh_frame = ctk.CTkFrame(voice_frame, fg_color="transparent")
        thresh_frame.pack(anchor="w", fill="x", pady=4)

        ctk.CTkLabel(
            thresh_frame, text="Manual Noise Threshold (used if dynamic is off): ",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left")

        thresh_entry = ctk.CTkEntry(
            thresh_frame, width=80, height=28,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["panel_border"],
            text_color=COLORS["text_primary"],
            font=ctk.CTkFont(size=11),
        )
        thresh_entry.pack(side="left", padx=10)
        thresh_entry.insert(0, str(self.config.get("energy_threshold", 300)))

        def toggle_thresh_state():
            if dynamic_var.get():
                thresh_entry.configure(state="disabled")
            else:
                thresh_entry.configure(state="normal")

        # Initial call to set correct entry state
        toggle_thresh_state()

        # Save & Cancel Buttons
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(16, 10))

        def save_settings():
            key = key_entry.get().strip()
            # Save API Key
            if key:
                self._save_config({"gemini_api_key": key})
                self.brain.set_api_key(key)

            # Save Sarvam API Key
            sarvam_key = sarvam_key_entry.get().strip()
            self._save_config({"sarvam_api_key": sarvam_key})

            # Save GNews API Key
            gnews_key = gnews_key_entry.get().strip()
            self._save_config({"gnews_api_key": gnews_key})


            # Save Mic index
            sel_mic = mic_dropdown.get()
            if sel_mic == "Default Microphone":
                self._save_config({"mic_device_index": None})
            else:
                try:
                    idx = mic_map.get(sel_mic, None)
                    self._save_config({"mic_device_index": idx})
                except Exception:
                    pass

            # Save Dynamic threshold
            dyn = dynamic_var.get()
            self._save_config({"dynamic_energy_threshold": dyn})

            # Save Language
            sel_lang = lang_dropdown.get()
            self._save_config({"recognition_language": lang_options.get(sel_lang, "en-US")})

            # Save Energy threshold
            try:
                thresh = int(thresh_entry.get().strip())
                self._save_config({"energy_threshold": thresh})
            except ValueError:
                pass

            # Save Wake-word enabled
            wake = wake_var.get()
            old_wake = self.config.get("wake_word_enabled", True)
            self._save_config({"wake_word_enabled": wake})

            # Re-apply configurations
            self._apply_voice_config()

            # Handle wake-word loop start/stop
            if wake != old_wake:
                if wake:
                    self._start_voice()
                else:
                    self._set_status("Click 🎤 or type command")

            win.destroy()
            self._set_status("Settings saved successfully.")

        ctk.CTkButton(
            btn_frame, text="Save Settings", width=200, height=38,
            fg_color=COLORS["accent"], hover_color="#2860d0",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            corner_radius=8,
            command=save_settings,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=38,
            fg_color=COLORS["btn_bg"], hover_color=COLORS["btn_hover"],
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            corner_radius=8,
            command=win.destroy,
        ).pack(side="left")

    # ── Clear chat ────────────────────────────────────────────────

    def _clear_chat(self):
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        self.chat_box.configure(state="disabled")
        self.brain.reset()
        self._set_status("Conversation cleared.")

    # ── Close ─────────────────────────────────────────────────────

    def _on_close(self):
        self._animating = False
        self.voice.stop()
        self.root.destroy()

    # ── Run ───────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
