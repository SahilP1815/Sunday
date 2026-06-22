import os
import json
import google.generativeai as genai
import requests
from pathlib import Path
from system_controller import handle_command


# ── Load API keys from config.json first, then fall back to env vars ──────────
_CONFIG_FILE = Path(__file__).parent / "config.json"

SARVAM_API_URL = "https://api.sarvam.ai/v1/chat/completions"
SARVAM_MODEL   = "sarvam-m"   # fast multilingual model; falls back to sarvam-30b
SARVAM_MODEL_FALLBACK = "sarvam-30b"


def _load_config() -> dict:
    """Read full config.json dict."""
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def _load_api_key() -> str:
    """Read Gemini API key from config.json, then environment variable."""
    key = _load_config().get("gemini_api_key", "").strip()
    return key or os.getenv("GEMINI_API_KEY", "").strip()


def _load_sarvam_key() -> str:
    """Read Sarvam API key from config.json, then environment variable."""
    key = _load_config().get("sarvam_api_key", "").strip()
    return key or os.getenv("SARVAM_API_KEY", "").strip()


def _load_tavily_key() -> str:
    """Read Tavily API key from config.json, then environment variable."""
    key = _load_config().get("tavily_api_key", "").strip()
    return key or os.getenv("TAVILY_API_KEY", "").strip()


SYSTEM_PROMPT = """You are Sunday, an intelligent and loyal personal AI assistant running natively on Windows.
You are modelled after J.A.R.V.I.S. — calm, precise, slightly witty, and deeply helpful.

Your capabilities:
- Open or close files, folders, or applications on the user's Windows PC (e.g. "close Chrome", "kill notepad")
- Control system settings (volume, brightness, media playback like play/pause/next, shutdown, lock, screenshot)
- Control application windows (minimize, maximize, close active window)
- Check real-time PC health diagnostics (CPU usage, RAM/memory, disk space, battery status)
- Open websites and URLs in the browser
- Answer questions, provide analysis, help with calculations
- Discuss news, weather, stocks, general knowledge
- Assist with writing, coding, and creative tasks
- Use tools to search the web, fetch real-time news, and check stock market/crypto prices when asked about current information.

Your personality:
- Address the user respectfully but warmly (you can use "sir" occasionally but don't overdo it)
- Be concise — give direct answers, avoid unnecessary padding
- When performing a system action, confirm it briefly ("Done. I've closed Notepad.")
- When unsure, say so honestly

You are speaking to the user through a voice interface. Keep responses conversational and clear.
Do NOT use markdown formatting like ** or # in your responses — speak naturally.
Keep responses under 3 sentences unless the user asks for more detail."""


# ── Tools ───────────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web for current events, news, or general search queries.
    
    Args:
        query: The search query string.
    """
    try:
        headers = {}
        if _CONFIG_FILE.exists():
            try:
                config_data = json.loads(_CONFIG_FILE.read_text())
                tavily_key = config_data.get("tavily_api_key", "").strip()
                if tavily_key:
                    headers["x-tavily-api-key"] = tavily_key
            except Exception:
                pass

        response = requests.get("http://localhost:3001/api/search", params={"q": query}, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if not results:
                return "No search results found."
            formatted = []
            for r in results[:4]:
                formatted.append(f"Title: {r.get('title')}\nSnippet: {r.get('snippet')}\nURL: {r.get('url')}\n")
            return "\n".join(formatted)
        return f"Error: Search API returned status code {response.status_code}"
    except Exception as e:
        return f"Error during web search: {str(e)}"

def get_market_data(symbol: str) -> str:
    """Get real-time stock market, index, cryptocurrency, or commodity prices.
    
    Args:
        symbol: The stock ticker or asset symbol (e.g., AAPL, nifty, btc, gold).
    """
    try:
        response = requests.get(f"http://localhost:3001/api/market/{symbol}", timeout=8)
        if response.status_code == 200:
            data = response.json()
            return (
                f"Asset: {data.get('name')} ({data.get('symbol')})\n"
                f"Price: {data.get('price')} {data.get('currency')}\n"
                f"Change: {data.get('change')} ({data.get('changePercent')}% {data.get('direction')})\n"
                f"Day Range: {data.get('dayLow')} - {data.get('dayHigh')}\n"
                f"Open: {data.get('open')} (Prev Close: {data.get('previousClose')})\n"
                f"Market State: {data.get('marketState')}\n"
                f"Timestamp: {data.get('timestamp')}"
            )
        return f"Error: Market API returned status code {response.status_code}"
    except Exception as e:
        return f"Error fetching market data: {str(e)}"

def get_news(category: str = "general") -> str:
    """Get the latest news headlines.
    
    Args:
        category: The category of news to fetch (e.g., general, business, technology, sports, science, health, entertainment).
    """
    try:
        headers = {}
        if _CONFIG_FILE.exists():
            try:
                config_data = json.loads(_CONFIG_FILE.read_text())
                gnews_key = config_data.get("gnews_api_key", "").strip()
                if gnews_key:
                    headers["x-gnews-api-key"] = gnews_key
                tavily_key = config_data.get("tavily_api_key", "").strip()
                if tavily_key:
                    headers["x-tavily-api-key"] = tavily_key
            except Exception:
                pass

        response = requests.get(
            "http://localhost:3001/api/news",
            params={"category": category},
            headers=headers,
            timeout=8
        )
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            if not articles:
                return f"No news articles found for category '{category}'."
            formatted = []
            for a in articles[:4]:
                formatted.append(f"Title: {a.get('title')}\nSource: {a.get('source')} ({a.get('publishedAt')})\nDescription: {a.get('description')}\nURL: {a.get('url')}\n")
            return "\n".join(formatted)
        return f"Error: News API returned status code {response.status_code}"
    except Exception as e:
        return f"Error fetching news: {str(e)}"


class SundayBrain:
    def __init__(self):
        self.history = []           # shared history for Sarvam (list of {role, content})
        self.model   = None         # Gemini GenerativeModel (fallback)
        self.chat    = None         # Gemini ChatSession (fallback)

        # Load keys
        self._api_key     = _load_api_key()    # Gemini key
        self._sarvam_key  = _load_sarvam_key() # Sarvam key (primary)
        self._tavily_key  = _load_tavily_key() # Tavily key

        # Init Gemini as fallback
        self._init_model()

        if self._sarvam_key:
            print(f"[Sunday Brain] Sarvam AI ready — using as primary brain ({SARVAM_MODEL}).")
        else:
            print("[Sunday Brain] No Sarvam key found — Gemini will handle all requests.")

    # ── Initialise Gemini (fallback) ──────────────────────────────

    def _get_best_model_name(self) -> str:
        """Find the best available Gemini model from list_models, or return default."""
        preferred_order = [
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]
        try:
            available_names = {m.name.split("/")[-1] for m in genai.list_models() if "generateContent" in m.supported_generation_methods}
            for pref in preferred_order:
                if pref in available_names:
                    print(f"[Sunday Brain] Gemini fallback model: {pref}")
                    return pref
            for name in sorted(available_names, reverse=True):
                if "flash" in name:
                    return name
            if available_names:
                return sorted(list(available_names))[0]
        except Exception as e:
            print(f"[Sunday Brain] Error listing Gemini models: {e}. Using default.")
        return "gemini-2.5-flash"

    def _init_model(self):
        """Configure and start a Gemini chat session (used as fallback)."""
        if not self._api_key:
            print("[Sunday Brain] No Gemini API key — fallback unavailable.")
            return
        try:
            genai.configure(api_key=self._api_key)
            model_name = self._get_best_model_name()
            self.model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=SYSTEM_PROMPT,
                tools=[web_search, get_market_data, get_news]
            )
            self.chat = self.model.start_chat(history=[], enable_automatic_function_calling=True)
            print(f"[Sunday Brain] Gemini fallback initialised: {model_name}")
        except Exception as e:
            print(f"[Sunday Brain] Failed to initialise Gemini fallback: {e}")
            self.model = None
            self.chat  = None

    # ── Sarvam AI (primary) ──────────────────────────────────────

    def _think_sarvam(self, user_message: str) -> str:
        """
        Send a message to Sarvam AI and return the reply.
        Maintains a rolling conversation history (last 10 turns).
        Raises an exception on failure so caller can fall back.
        """
        # Build message list: system + history + new user turn
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self.history[-20:]  # last 10 turns (20 entries)
        messages.append({"role": "user", "content": user_message})

        headers = {
            "api-subscription-key": self._sarvam_key,
            "Content-Type": "application/json"
        }
        payload = {
            "model": SARVAM_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 512
        }

        response = requests.post(
            SARVAM_API_URL,
            json=payload,
            headers=headers,
            timeout=15
        )

        if response.status_code == 404:
            # Model not found — try the fallback model name
            payload["model"] = SARVAM_MODEL_FALLBACK
            response = requests.post(
                SARVAM_API_URL,
                json=payload,
                headers=headers,
                timeout=15
            )

        if response.status_code not in (200, 201):
            raise Exception(f"Sarvam API error {response.status_code}: {response.text[:200]}")

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()

        # Persist to shared history
        self._log(user_message, reply)
        return reply

    # ── Public API ────────────────────────────────────────────

    def set_api_key(self, api_key: str):
        """Update Gemini API key, persist it to config.json, and reinitialise."""
        self._api_key = api_key.strip()
        try:
            data = _load_config()
            data["gemini_api_key"] = self._api_key
            _CONFIG_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[Sunday Brain] Could not save Gemini key: {e}")
        os.environ["GEMINI_API_KEY"] = self._api_key
        self.history = []
        self._init_model()

    def set_sarvam_key(self, sarvam_key: str):
        """Update Sarvam API key, persist it to config.json."""
        self._sarvam_key = sarvam_key.strip()
        try:
            data = _load_config()
            data["sarvam_api_key"] = self._sarvam_key
            _CONFIG_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[Sunday Brain] Could not save Sarvam key: {e}")
        os.environ["SARVAM_API_KEY"] = self._sarvam_key
        self.history = []
        if self._sarvam_key:
            print(f"[Sunday Brain] Sarvam key updated. Now using Sarvam as primary brain.")

    def set_tavily_key(self, tavily_key: str):
        """Update Tavily API key, persist it to config.json."""
        self._tavily_key = tavily_key.strip()
        try:
            data = _load_config()
            data["tavily_api_key"] = self._tavily_key
            _CONFIG_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[Sunday Brain] Could not save Tavily key: {e}")
        os.environ["TAVILY_API_KEY"] = self._tavily_key

    def is_ready(self) -> bool:
        """Ready if either Sarvam key OR Gemini chat is available."""
        return bool(self._sarvam_key) or (self.model is not None and self.chat is not None)

    def think(self, user_message: str) -> str:
        """
        Process a message:
        1. Try local system command handler first.
        2. Try Sarvam AI (primary brain) if key is configured.
        3. Fall back to Gemini if Sarvam fails or key is absent.
        """
        # Step 1 — system command handler (volume, open app, etc.)
        system_result = handle_command(user_message)
        if system_result:
            self._log(user_message, system_result)
            return system_result

        # Step 2 — Sarvam AI (primary)
        if self._sarvam_key:
            try:
                reply = self._think_sarvam(user_message)
                return reply
            except Exception as e:
                err = str(e)
                print(f"[Sunday Brain] Sarvam failed: {err}. Falling back to Gemini.")
                if "401" in err or "403" in err or "invalid_api_key" in err.lower():
                    # Bad key — clear it so we don't keep hammering Sarvam
                    self._sarvam_key = ""
                    print("[Sunday Brain] Sarvam key appears invalid. Switched to Gemini.")

        # Step 3 — Gemini fallback
        if not (self.model and self.chat):
            # Try lazy init in case key was added after startup
            self._api_key = _load_api_key()
            if self._api_key:
                self._init_model()

        if not (self.model and self.chat):
            return ("I'm not connected to any AI core. "
                    "Please add your Sarvam or Gemini API key in the Settings panel.")

        try:
            response = self.chat.send_message(user_message)
            reply = response.text.strip()
            self._log(user_message, reply)
            return reply
        except Exception as e:
            err = str(e)
            if "API_KEY" in err.upper() or "401" in err or "403" in err:
                return "My Gemini API key appears to be invalid. Please update it in Settings."
            if "quota" in err.lower() or "429" in err:
                return "I've hit my API quota limit. Please try again in a moment."
            return f"I encountered an error: {err[:120]}"

    def reset(self):
        """Clear conversation history and start fresh."""
        self.history = []
        if self.model:
            self.chat = self.model.start_chat(history=[], enable_automatic_function_calling=True)

    # ── Internal ───────────────────────────────────────────────

    def _log(self, user_msg: str, assistant_msg: str):
        self.history.append({"role": "user",      "content": user_msg})
        self.history.append({"role": "assistant",  "content": assistant_msg})
