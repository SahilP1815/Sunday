"""
Sunday Voice Engine
Handles STT (speech-to-text) via SpeechRecognition / Sarvam AI and TTS via pyttsx3 / Sarvam AI.
Runs in background threads to keep the UI responsive.
"""

import threading
import queue
import speech_recognition as sr
import pyttsx3
import requests
import base64
import io
import wave
import pyaudio


WAKE_WORDS = ["sunday", "hey sunday", "ok sunday"]


class VoiceEngine:
    def __init__(self, on_wake=None, on_transcript=None, on_error=None, on_interim=None):
        """
        on_wake       : called with the wake phrase text that was detected
        on_transcript : called with final transcript string
        on_error      : called with error string
        on_interim    : called with interim (partial) transcript while listening
        """
        self.on_wake       = on_wake     or (lambda text: None)
        self.on_transcript = on_transcript or (lambda t: None)
        self.on_error      = on_error    or (lambda e: None)
        self.on_interim    = on_interim  or (lambda t: None)

        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.recognizer.energy_threshold = 350
        self.wake_word_enabled = True
        self.device_index = None
        self.language = "en-US"
        self.sarvam_api_key = ""

        self._tts_engine   = None
        self._tts_lock     = threading.Lock()
        self._tts_queue    = queue.Queue()
        self._tts_thread   = None

        self._listening    = False
        self._active       = False  # True = full listening (post wake-word)
        self._calibrated   = False
        self._speaking     = False
        self._wake_thread  = None
        self._active_thread = None
        self._stop_event   = threading.Event()
        self._stop_speech_event = threading.Event()

        self._init_tts()

    # ── TTS ──────────────────────────────────────────────────────

    def _init_tts(self):
        """Initialize pyttsx3 in a dedicated thread."""
        def _run():
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", 165)
            self._tts_engine.setProperty("volume", 0.95)
            # Prefer a British English voice if available
            voices = self._tts_engine.getProperty("voices")
            preferred = None
            for v in voices:
                if "english" in v.name.lower() and ("uk" in v.id.lower() or "zira" in v.name.lower()):
                    preferred = v.id
                    break
            if not preferred and voices:
                preferred = voices[0].id
            if preferred:
                self._tts_engine.setProperty("voice", preferred)

            # Process TTS queue
            while not self._stop_event.is_set():
                try:
                    text = self._tts_queue.get(timeout=0.2)
                    if text is None:
                        break
                    
                    self._stop_speech_event.clear()
                    self._speaking = True
                    try:
                        # Try speaking via Sarvam AI if configured
                        success = False
                        if self.sarvam_api_key:
                            success = self._speak_sarvam(text)
                            
                        if not success:
                            self._tts_engine.say(text)
                            self._tts_engine.runAndWait()
                    finally:
                        self._speaking = False
                        self._tts_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[TTS] Error: {e}")

        self._tts_thread = threading.Thread(target=_run, daemon=True)
        self._tts_thread.start()

    def speak(self, text: str):
        """Queue text for speaking (non-blocking)."""
        print(f"[Sunday] {text}")
        self._tts_queue.put(text)

    def stop_speaking(self):
        """Stop current speech immediately."""
        self._stop_speech_event.set()
        if self._tts_engine:
            try:
                self._tts_engine.stop()
            except Exception:
                pass

    def _speak_sarvam(self, text: str) -> bool:
        """Speak via Sarvam AI. Returns True if successful, False otherwise."""
        if not self.sarvam_api_key:
            return False
        
        try:
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {
                "api-subscription-key": self.sarvam_api_key,
                "Content-Type": "application/json"
            }
            
            # Map recognition language to target language for TTS
            lang = self.language
            if not lang:
                lang = "hi-IN"
            elif "en" in lang.lower():
                lang = "en-IN"
            elif "hi" in lang.lower():
                lang = "hi-IN"

            # Speaker choice: e.g., shubh for English, sarika for Hindi
            speaker = "shubh" if "en" in lang else "sarika"
            
            payload = {
                "text": text,
                "speaker": speaker,
                "target_language_code": lang,
                "model": "bulbul:v3"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"[Sarvam TTS] API returned status {response.status_code}: {response.text}")
                return False
                
            data = response.json()
            if "audios" not in data or not data["audios"]:
                return False
                
            audio_b64 = data["audios"][0]
            audio_bytes = base64.b64decode(audio_b64)
            
            # Play via PyAudio
            f = io.BytesIO(audio_bytes)
            with wave.open(f, 'rb') as wav_file:
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=p.get_format_from_width(wav_file.getsampwidth()),
                    channels=wav_file.getnchannels(),
                    rate=wav_file.getframerate(),
                    output=True
                )
                
                chunk = 1024
                # Check for stop events during playback so user can interrupt
                play_data = wav_file.readframes(chunk)
                while play_data and not self._stop_speech_event.is_set() and not self._stop_event.is_set():
                    stream.write(play_data)
                    play_data = wav_file.readframes(chunk)
                    
                stream.stop_stream()
                stream.close()
                p.terminate()
            return True
        except Exception as e:
            print(f"[Sarvam TTS] Error: {e}")
            return False

    # ── Wake-word listening ───────────────────────────────────────

    def start_wake_word_listening(self):
        """Start background thread that listens for wake word."""
        if self._listening:
            return
        self._listening = True
        self._stop_event.clear()
        self._wake_thread = threading.Thread(target=self._wake_word_loop, daemon=True)
        self._wake_thread.start()
        print("[Voice] Wake-word listener started.")

    def calibrate(self):
        """Calibrate the microphone for ambient noise once to ignore background noise."""
        try:
            print("[Voice] Calibrating microphone for ambient noise...")
            with sr.Microphone(device_index=self.device_index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            # Clamp threshold to prevent it from being too sensitive in quiet environments
            if self.recognizer.energy_threshold < 350:
                self.recognizer.energy_threshold = 350
            self._calibrated = True
            print(f"[Voice] Calibration complete. Energy threshold set to {self.recognizer.energy_threshold}")
        except Exception as e:
            print(f"[Voice] Microphone calibration failed: {e}")

    def reset_calibration(self):
        """Reset calibration state."""
        self._calibrated = False

    def _wake_word_loop(self):
        """Continuously listen for wake word."""
        while self._listening and not self._stop_event.is_set():
            if not self.wake_word_enabled:
                threading.Event().wait(0.5)
                continue
            if self._active or self._speaking:
                # Full listening or speaking is active, don't double-listen
                threading.Event().wait(0.5)
                continue
            
            # Calibrate once before starting to listen in the loop
            if not self._calibrated:
                self.calibrate()
                
            try:
                with sr.Microphone(device_index=self.device_index) as source:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=4)
                try:
                    text = self.recognizer.recognize_google(audio, language=self.language).lower()
                    print(f"[Wake] Heard: '{text}'")
                    if any(w in text for w in WAKE_WORDS):
                        self.on_wake(text)          # pass the detected phrase
                        self._listen_for_command()
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    self.on_error(f"Speech service error: {e}")
            except sr.WaitTimeoutError:
                pass
            except OSError as e:
                self.on_error(f"Microphone error: {e}")
                threading.Event().wait(2)
            except Exception as e:
                print(f"[Wake] Unexpected error: {e}")
                threading.Event().wait(1)

    # ── Active listening ──────────────────────────────────────────

    def listen_once(self):
        """Manually trigger one-shot listening (button press)."""
        if self._active:
            return
        thread = threading.Thread(target=self._listen_for_command, daemon=True)
        thread.start()

    def _listen_for_command(self):
        """Listen for a full command after activation."""
        self._active = True
        try:
            if not self._calibrated:
                self.calibrate()
            with sr.Microphone(device_index=self.device_index) as source:
                # Single listen call — captures the whole command
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)

            # Recognise — show interim text while processing
            self.on_interim("recognising...")
            try:
                if self.sarvam_api_key:
                    try:
                        text = self._transcribe_sarvam(audio)
                        print(f"[Active] Heard (Sarvam): '{text}'")
                    except Exception as ex:
                        print(f"[Active] Sarvam STT failed: {ex}. Falling back to Google.")
                        text = self.recognizer.recognize_google(audio, language=self.language)
                else:
                    text = self.recognizer.recognize_google(audio, language=self.language)
                    print(f"[Active] Heard: '{text}'")
                
                self.on_interim(text)          # flash final text briefly
                self.on_transcript(text)
                self.on_interim("")            # clear after handing off
            except sr.UnknownValueError:
                self.on_interim("")
                self.on_error("I didn't catch that. Please try again.")
            except sr.RequestError as e:
                self.on_interim("")
                self.on_error(f"Could not connect to speech service: {e}")
        except sr.WaitTimeoutError:
            self.on_interim("")
            self.on_error("No speech detected.")
        except OSError as e:
            self.on_error(f"Microphone not found: {e}")
        except Exception as e:
            self.on_error(f"Voice error: {e}")
        finally:
            self._active = False

    def _transcribe_sarvam(self, audio: sr.AudioData) -> str:
        """Transcribe audio via Sarvam STT API."""
        if not self.sarvam_api_key:
            raise ValueError("No Sarvam API key provided")
            
        url = "https://api.sarvam.ai/speech-to-text"
        headers = {
            "api-subscription-key": self.sarvam_api_key
        }
        
        # Get WAV bytes from SpeechRecognition AudioData
        wav_data = audio.get_wav_data()
        
        # Prepare multipart/form-data payload
        files = {
            'file': ('audio.wav', wav_data, 'audio/wav')
        }
        data = {
            'model': 'saaras:v3',
            'mode': 'transcribe'
        }
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Sarvam STT API returned status {response.status_code}: {response.text}")
            
        res_data = response.json()
        return res_data.get("transcript", "").strip()

    def stop(self):
        """Stop all voice activity."""
        self._listening = False
        self._active    = False
        self._stop_event.set()
        self._tts_queue.put(None)
        self.stop_speaking()
