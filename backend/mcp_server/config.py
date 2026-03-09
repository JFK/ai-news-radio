"""MCP server configuration."""

import os

BACKEND_URL = os.environ.get("AINEWSRADIO_BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = float(os.environ.get("AINEWSRADIO_TIMEOUT", "120"))
