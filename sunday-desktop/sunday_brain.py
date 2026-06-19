import os
import json
import google.generativeai as genai
import requests
from pathlib import Path
from system_controller import handle_command


# ── Load API key from config.json first, then fall back to env var ────────────
_CONFIG_FILE = Path(__file__).parent / "config.json"


def _load_api_key() -> str:
    """Read Gemini API key from config.json, then environment variable."""
    # 1. config.json (written by the Settings dialog)
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text())
            key = data.get("gemini_api_key", "").strip()
            if key:
                return key
        except Exception:
            pass
    # 2. Environment variable fallback
    return os.getenv("GEMINI_API_KEY", "").strip()


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
        response = requests.get("http://localhost:3001/api/search", params={"q": query}, timeout=8)
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
        response = requests.get("http://localhost:3001/api/news", params={"category": category}, timeout=8)
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
        self.history = []
        self.model   = None
        self.chat    = None
        # Load key from config.json / env and initialise immediately
        self._api_key = _load_api_key()
        self._init_model()

    # ── Initialise Gemini ─────────────────────────────────────────

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
                    print(f"[Sunday Brain] Found preferred model: {pref}")
                    return pref
            # Fallback to any flash model
            for name in sorted(available_names, reverse=True):
                if "flash" in name:
                    print(f"[Sunday Brain] Falling back to available flash model: {name}")
                    return name
            # Fallback to any model
            if available_names:
                any_model = sorted(list(available_names))[0]
                print(f"[Sunday Brain] Falling back to model: {any_model}")
                return any_model
        except Exception as e:
            print(f"[Sunday Brain] Error listing models: {e}. Using default.")
        
        return "gemini-3.5-flash"

    def _init_model(self):
        """Configure and start a Gemini chat session."""
        if not self._api_key:
            print("[Sunday Brain] No Gemini API key found. "
                  "Add it via Settings or put it in config.json.")
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
            print(f"[Sunday Brain] Gemini initialised successfully with model: {model_name}")
        except Exception as e:
            print(f"[Sunday Brain] Failed to initialise Gemini: {e}")
            self.model = None
            self.chat  = None


    # ── Public API ────────────────────────────────────────────────

    def set_api_key(self, api_key: str):
        """Update API key, persist it to config.json, and reinitialise."""
        self._api_key = api_key.strip()
        # Persist so it survives restarts
        try:
            data = json.loads(_CONFIG_FILE.read_text()) if _CONFIG_FILE.exists() else {}
            data["gemini_api_key"] = self._api_key
            _CONFIG_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[Sunday Brain] Could not save API key: {e}")
        # Also set in env for any library that reads it
        os.environ["GEMINI_API_KEY"] = self._api_key
        self.history = []
        self._init_model()

    def is_ready(self) -> bool:
        return self.model is not None and self.chat is not None

    def think(self, user_message: str) -> str:
        """
        Process a message:
        1. Try local system command handler first.
        2. Fall back to Gemini for everything else.
        """
        # System command
        system_result = handle_command(user_message)
        if system_result:
            self._log(user_message, system_result)
            return system_result

        # Gemini
        if not self.is_ready():
            # One more attempt to load the key in case it was added after startup
            self._api_key = _load_api_key()
            if self._api_key:
                self._init_model()
            if not self.is_ready():
                return ("I'm not connected to my AI core. "
                        "Please add your Gemini API key in the Settings panel.")
        try:
            response = self.chat.send_message(user_message)
            reply = response.text.strip()
            return reply
        except Exception as e:
            err = str(e)
            if "API_KEY" in err.upper() or "401" in err or "403" in err:
                return "My API key appears to be invalid. Please update it in Settings."
            if "quota" in err.lower() or "429" in err:
                return "I've hit my API quota limit. Please try again in a moment."
            return f"I encountered an error: {err[:120]}"

    def reset(self):
        """Clear conversation history and start a fresh chat."""
        self.history = []
        if self.model:
            self.chat = self.model.start_chat(history=[], enable_automatic_function_calling=True)

    # ── Internal ──────────────────────────────────────────────────

    def _log(self, user_msg: str, assistant_msg: str):
        self.history.append({"role": "user",      "content": user_msg})
        self.history.append({"role": "assistant",  "content": assistant_msg})
