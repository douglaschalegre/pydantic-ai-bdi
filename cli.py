"""CLI entry points for the BDI agent."""

import subprocess
import sys


def start():
    """Start the development server."""
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "server.app:app", "--reload", "--port", "8000"]
    )


if __name__ == "__main__":
    start()
