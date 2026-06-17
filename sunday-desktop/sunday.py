"""
Sunday Desktop AI Assistant
Native Windows desktop app with voice, Gemini AI, and system control.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sunday_app import SundayApp

if __name__ == "__main__":
    app = SundayApp()
    app.run()
