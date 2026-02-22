#!/usr/bin/env python3
"""
GI Copilot - Startup Script
Launches the server with Cloudflare tunnel for HTTPS
"""

import sys
import os
import subprocess
import time
import signal
import shutil
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000
DOMAIN = "medvisor.fyi"
TUNNEL_NAME = "medvisor"
APP_DIR = Path("/workspace/doc_copilot")
# ──────────────────────────────────────────────────────────────────────────────


processes = []  # track background processes for cleanup


def banner():
    print("""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║              🏥 GI COPILOT STARTUP                   ║
║         with Cloudflare Tunnel (HTTPS)               ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """)


def cleanup(signum=None, frame=None):
    print("\n\n🛑 Shutting down...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("✅ All processes stopped")
    sys.exit(0)


# Register signal handlers so Ctrl+C cleans up everything
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


# ── Checks ────────────────────────────────────────────────────────────────────

def check_dependencies():
    required = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'sqlalchemy': 'sqlalchemy',
        'cv2': 'opencv-python',
        'PIL': 'pillow'
    }
    missing = [pkg for mod, pkg in required.items() if not _can_import(mod)]
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)}")
        return False
    print("✅ Python dependencies OK")
    return True


def _can_import(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def check_environment():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("⚠️  OPENAI_API_KEY not set — voice chat will not work")
        print("   Set with: export OPENAI_API_KEY='sk-...'")
        answer = input("   Continue anyway? (y/n): ").strip().lower()
        return answer == 'y'
    print("✅ OPENAI_API_KEY found")
    return True


def check_files():
    required = [
        'main_app.py', 'index.html', 'app.js',
        'database.py', 'models.py', 'storage_service.py',
        'routes_video.py', 'gi.py'
    ]
    missing = [f for f in required if not (APP_DIR / f).exists()]
    if missing:
        print(f"❌ Missing files: {', '.join(missing)}")
        return False

    # Copy app.js → static/
    static = APP_DIR / 'static'
    static.mkdir(exist_ok=True)
    shutil.copy(APP_DIR / 'app.js', static / 'app.js')
    print("✅ Files OK  (app.js → static/)")
    return True


def create_directories():
    for d in ['data', 'data/storage', 'static']:
        (APP_DIR / d).mkdir(parents=True, exist_ok=True)
    print("✅ Directories OK")


def check_cloudflared():
    """Return True if cloudflared is installed and tunnel config exists."""
    if not shutil.which('cloudflared'):
        print("⚠️  cloudflared not found — skipping tunnel")
        print("   Install with:")
        print("   curl -L https://github.com/cloudflare/cloudflared/releases/"
              "latest/download/cloudflared-linux-amd64 "
              "-o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared")
        return False

    config = Path.home() / '.cloudflared' / 'config.yml'
    if not config.exists():
        print("⚠️  Cloudflare tunnel not configured (~/.cloudflared/config.yml missing)")
        print("   Run setup steps first (cloudflared tunnel create ...)")
        return False

    # Sanity-check: make sure $TUNNEL_ID was actually substituted
    content = config.read_text()
    if '$TUNNEL_ID' in content:
        print("❌ ~/.cloudflared/config.yml still contains '$TUNNEL_ID'")
        print("   Replace it with your actual tunnel UUID")
        print("   Run: cloudflared tunnel list   to get your UUID")
        return False

    print("✅ cloudflared config found")
    return True


# ── Launchers ─────────────────────────────────────────────────────────────────

def start_app():
    """Start uvicorn as a subprocess."""
    print(f"\n🚀 Starting FastAPI on port {PORT}...")
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main_app:app',
         '--host', HOST, '--port', str(PORT),
         '--reload', '--log-level', 'info'],
        cwd=APP_DIR
    )
    processes.append(proc)
    return proc


def start_tunnel():
    """Start the Cloudflare tunnel."""
    print(f"\n🌐 Starting Cloudflare Tunnel → https://{DOMAIN} ...")
    proc = subprocess.Popen(
        ['cloudflared', 'tunnel', '--config',
         str(Path.home() / '.cloudflared' / 'config.yml'),
         'run', TUNNEL_NAME],
        cwd=APP_DIR
    )
    processes.append(proc)
    return proc


def wait_for_app(timeout=30):
    """Poll localhost until the app responds."""
    import urllib.request
    print(f"⏳ Waiting for app to be ready", end='', flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(
                f'http://localhost:{PORT}/api/gi/timeline', timeout=2)
            print(" ✅")
            return True
        except Exception:
            print('.', end='', flush=True)
            time.sleep(1)
    print(" ⚠️  (timeout)")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    banner()
    os.chdir(APP_DIR)

    print("🔍 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)

    print("\n🔍 Checking environment...")
    if not check_environment():
        sys.exit(1)

    print("\n📁 Setting up directories...")
    create_directories()

    print("\n🔍 Checking files...")
    if not check_files():
        sys.exit(1)

    tunnel_available = check_cloudflared()

    # ── Start app ──
    app_proc = start_app()
    wait_for_app()

    # ── Start tunnel if configured ──
    tunnel_proc = None
    if tunnel_available:
        tunnel_proc = start_tunnel()
        print(f"\n{'='*60}")
        print(f"  🏥 GI Copilot is live at:")
        print(f"  🌐 https://{DOMAIN}             ← use this!")
        print(f"  🏠 http://localhost:{PORT}        (local only)")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print(f"  🏥 GI Copilot running (no HTTPS tunnel):")
        print(f"  🏠 http://localhost:{PORT}")
        print(f"  ⚠️  Voice chat may not work without HTTPS")
        print(f"  💡 Set up Cloudflare tunnel to enable HTTPS")
        print(f"{'='*60}\n")

    print("Press Ctrl+C to stop\n")

    # ── Monitor — restart crashed processes ──
    while True:
        time.sleep(5)

        if app_proc.poll() is not None:
            print("⚠️  App crashed — restarting...")
            processes.remove(app_proc)
            app_proc = start_app()

        if tunnel_proc and tunnel_proc.poll() is not None:
            print("⚠️  Tunnel crashed — restarting...")
            processes.remove(tunnel_proc)
            tunnel_proc = start_tunnel()


if __name__ == "__main__":
    main()