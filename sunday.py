"""
Sunday AI Assistant — Unified Launcher
Starts the Node.js backend server in the background and runs the CustomTkinter desktop application.
Automatically shuts down the backend server when the GUI is closed.
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

def get_startupinfo():
    """Configure startupinfo to run the subprocess silently on Windows."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0 # SW_HIDE
        return startupinfo
    return None

def run_backend():
    """Start the Node.js backend server as a background subprocess."""
    backend_dir = Path(__file__).parent / "sunday-backend"
    if not backend_dir.exists():
        print("[Launcher] sunday-backend directory not found. Skipping backend startup.")
        return None

    # Check if node is installed
    try:
        subprocess.run(["node", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[Launcher] Node.js is not installed or not in PATH. Skipping backend startup.")
        return None

    # Install dependencies if node_modules doesn't exist
    if not (backend_dir / "node_modules").exists():
        print("[Launcher] Node modules not found. Running npm install...")
        try:
            subprocess.run("npm install", shell=True, cwd=str(backend_dir), check=True)
        except Exception as e:
            print(f"[Launcher] Failed to install Node modules: {e}")
            return None

    print("[Launcher] Starting Sunday Web Backend on Port 3001...")
    try:
        # Launch node server.js
        process = subprocess.Popen(
            ["node", "server.js"],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=get_startupinfo(),
            shell=True
        )

        # Non-blocking reader thread for stdout/stderr logs
        def log_stream(stream, prefix):
            try:
                for line in iter(stream.readline, ''):
                    if line:
                        print(f"[{prefix}] {line.strip()}")
            except Exception:
                pass
            finally:
                stream.close()

        threading.Thread(target=log_stream, args=(process.stdout, "Backend"), daemon=True).start()
        threading.Thread(target=log_stream, args=(process.stderr, "Backend Error"), daemon=True).start()

        return process
    except Exception as e:
        print(f"[Launcher] Error starting backend subprocess: {e}")
        return None

def main():
    # 1. Start the Node.js Web Backend
    backend_proc = run_backend()
    if backend_proc:
        # Give it a second to bind to the port
        time.sleep(1.5)

    # 2. Add sunday-desktop directory to system path
    desktop_dir = Path(__file__).parent / "sunday-desktop"
    if not desktop_dir.exists():
        print(f"[Launcher] ERROR: Desktop directory not found at {desktop_dir}")
        sys.exit(1)
    
    sys.path.insert(0, str(desktop_dir))

    # 3. Launch Desktop Application
    try:
        from sunday_app import SundayApp
        print("[Launcher] Launching Sunday Desktop Assistant UI...")
        app = SundayApp()
        app.run()
    except Exception as e:
        print(f"[Launcher] Error running Sunday Desktop App: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 4. Clean up background backend process when GUI exits
        if backend_proc:
            print("[Launcher] Terminating background Sunday Web Backend...")
            try:
                if os.name == 'nt':
                    # Use taskkill to kill the subprocess and all its children
                    subprocess.run(
                        f"taskkill /F /T /PID {backend_proc.pid}",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    backend_proc.terminate()
                    backend_proc.wait(timeout=2)
            except Exception as e:
                print(f"[Launcher] Warning: Failed to stop backend process cleanly: {e}")
            print("[Launcher] Cleanup complete. Exiting.")

if __name__ == "__main__":
    main()
