"""Run the web app locally: python -m server [--mock] [--port 8000] [--no-browser]"""
import argparse
import os
import threading
import webbrowser
from pathlib import Path

import uvicorn

p = argparse.ArgumentParser(description="AI TTRPG Runner — local web app")
p.add_argument("--mock", action="store_true", help="offline scripted Keeper, no API key needed")
p.add_argument("--port", type=int, default=8000)
p.add_argument("--no-browser", action="store_true")
args = p.parse_args()

if args.mock:
    os.environ["MOCK_LLM"] = "1"
if not (Path(__file__).resolve().parent.parent / "web" / "dist" / "index.html").exists():
    print("web/dist is missing — build the frontend first:  cd web && npm install && npm run build")

url = f"http://127.0.0.1:{args.port}"
print(f"AI TTRPG Runner on {url}")
if not args.no_browser:
    threading.Timer(1.5, webbrowser.open, [url]).start()
# ponytail: localhost only — there's no login. Bind to the LAN once online rooms have auth.
uvicorn.run("server.app:app", host="127.0.0.1", port=args.port)
