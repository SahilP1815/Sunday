# Sunday — JARVIS-inspired Personal AI Assistant

Sunday is a futuristic, voice-enabled, personal AI assistant designed to run locally on Windows. Inspired by JARVIS, Sunday consists of three main components:
1. **Desktop Client (`sunday-desktop`)**: A native Windows application with a CustomTkinter GUI, Speech Recognition, and local system automation capabilities.
2. **Backend Server (`sunday-backend`)**: A robust Node.js/Express service that proxies requests to Anthropic (Claude), Yahoo Finance, GNews, SerpAPI, and Sarvam AI.
3. **Web Client (`sunday_ai_agent.html`)**: A futuristic, single-page web interface featuring an interactive glowing voice orb and a space-like background, connecting seamlessly to the Sunday backend.

---

## Architecture & Project Structure

```
Sunday/
├── sunday-desktop/          # Python CustomTkinter Desktop Client
│   ├── sunday.py            # App Entry point
│   ├── sunday_app.py        # Main CustomTkinter UI logic
│   ├── sunday_brain.py      # LLM integration (Gemini) & prompt logic
│   ├── system_controller.py # Windows automation & system commands
│   ├── voice_engine.py      # Speech-to-text (STT) and Text-to-speech (TTS)
│   ├── requirements.txt     # Python dependencies
│   ├── config.json.example  # Example config file (rename to config.json)
│   ├── install.bat          # Installation script
│   └── run.bat              # Run script
│
├── sunday-backend/          # Node.js/Express Backend Server
│   ├── server.js            # Main Express server & API routes
│   ├── config/              # Server configuration
│   ├── routes/              # API Route definitions (news, stocks, search, chat)
│   ├── middleware/          # Express middleware (rate limiting, validation)
│   ├── package.json         # Node.js package definition
│   ├── .env.example         # Example environment variables (rename to .env)
│   └── node_modules/        # Ignored (Node dependencies)
│
├── sunday_ai_agent.html     # Single-page futuristic web interface
└── .gitignore               # Standard git ignore rules
```

---

## Features

### 🎙️ Advanced Voice Control
- **Wake Word Recognition**: Wake up Sunday hands-free by saying `"Hey Sunday"`.
- **Text-to-Speech (TTS)**: Clean, customizable speech feedback powered by local engines or **Sarvam AI (Bulbul v3)**.
- **Speech-to-Text (STT)**: High-quality local recognition with fallbacks to **Sarvam AI (Saaras v3)** for multilingual Indian support.

### 💻 Windows Native Automation (`system_controller.py`)
Control your computer using voice or text commands:
- **Application Launching**: Launch popular apps like Google Chrome, VS Code, Cursor, Spotify, Discord, Telegram, Whatsapp, Steam, VLC, Zoom, etc.
- **System Tools**: Access Notepad, Calculator, Task Manager, File Explorer, Command Prompt, Device Manager, Control Panel, and Settings.
- **System Power Controls**: Control shutting down, restarting, cancelling shut down, or locking your computer.
- **Volume & Media**: Increase, decrease, or mute system audio.
- **Screenshots**: Automatically trigger the Windows Snipping Tool (`Win + Shift + S`).
- **File Finder & Navigator**: Search and locate specific files and folders inside common directories (Desktop, Documents, Downloads, etc.) or list folder contents.

### 🌐 Intelligent Integrations
- **Stock Market Analysis**: Fetch live stock quotes via Yahoo Finance.
- **World News**: Keep track of current events globally via GNews.
- **Web Search**: Fallback searches using SerpAPI or DuckDuckGo Instant Answers.
- **Dual LLM Engines**: Connects to Anthropic Claude (via the backend) and Google Gemini (locally on desktop).

---

## Getting Started

### 1. Backend Setup (`sunday-backend`)
The backend manages API integrations and connects Sunday to Anthropic Claude, Yahoo Finance, GNews, and Sarvam AI.

1. Navigate to the `sunday-backend` directory.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Copy `.env.example` to `.env` and configure your API keys:
   ```bash
   copy .env.example .env
   ```
   *Required:* Fill in your `ANTHROPIC_API_KEY`.
   *Optional:* Add `GNEWS_API_KEY`, `SERPAPI_KEY`, and `SARVAM_API_KEY`.
4. Run the backend server in development mode:
   ```bash
   npm run dev
   ```
   The backend will start at `http://localhost:3001`.

### 2. Desktop Client Setup (`sunday-desktop`)
The desktop client handles the local GUI, voice interactions, and Windows automation.

1. Navigate to the `sunday-desktop` directory.
2. Install Python dependencies (requires Python 3.9+):
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `config.json.example` to `config.json` and enter your Gemini API key:
   ```json
   {
     "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE"
   }
   ```
4. Run the desktop application:
   ```bash
   python sunday.py
   ```
   *Alternatively, run `install.bat` once to set up, and launch via `run.bat`.*

### 3. Web Client Setup (`sunday_ai_agent.html`)
To run the lightweight web-based interface:
1. Double-click or open `sunday_ai_agent.html` in any modern web browser.
2. Enter your backend URL (e.g., `http://localhost:3001`).
3. Click **Connect & Activate** to start interacting!

---

## Technology Stack

- **Desktop**: Python 3, CustomTkinter, PyAudio, pyttsx3, SpeechRecognition, google-generativeai, pywin32, psutil
- **Backend**: Node.js, Express, Axios, @anthropic-ai/sdk, @google/generative-ai, yahoo-finance2
- **Web**: Vanilla HTML5, CSS3 (Glassmorphism & animations), ES6 Javascript
- **APIs**: Anthropic Claude, Google Gemini, Yahoo Finance, GNews, SerpAPI, Sarvam AI

## License
MIT
