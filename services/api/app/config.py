from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

DEMO_MODE = env("DEMO_MODE", "true").lower() == "true"
DATABASE_PATH = Path(env("DATABASE_PATH", str(ROOT / "lifepilot.db")))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT / DATABASE_PATH
API_SECRET = env("API_SECRET", "development-only-change-me")
MCP_MODE = env("MCP_MODE", "stdio")
FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", "http://localhost:3000")
