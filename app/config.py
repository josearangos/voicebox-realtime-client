import os

VOICEBOX_URL = os.environ.get("VOICEBOX_URL", "http://127.0.0.1:17493").rstrip("/")
HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "7860"))

CONNECT_TIMEOUT_S = 3.0
DISCOVERY_READ_TIMEOUT_S = 10.0
CHUNK_READ_TIMEOUT_S = 120.0

MAX_TEXT_CHARS = 5000
