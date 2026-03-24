"""Client for the background TTS model server.

Connects to the Unix socket, sends a generation request, and returns
audio samples. Falls back gracefully if the server isn't running.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

_SOCK_DIR = Path("/tmp")
_CONNECT_TIMEOUT = 5.0  # seconds to wait for server to start
_REQUEST_TIMEOUT = 30.0  # seconds to wait for generation


def _socket_path() -> Path:
    return _SOCK_DIR / f"sag-{os.getuid()}.sock"


def _pid_path() -> Path:
    return _SOCK_DIR / f"sag-{os.getuid()}.pid"


def _server_alive() -> bool:
    """Check if a server process is running."""
    pid_path = _pid_path()
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, PermissionError, OSError):
        return False


def _start_server() -> bool:
    """Spawn the server as a detached background process. Returns True if started."""
    try:
        # Find the sag executable
        import shutil

        sag_bin = shutil.which("sag")
        if not sag_bin:
            return False

        # Start server detached from this process
        subprocess.Popen(
            [sag_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def ensure_server() -> bool:
    """Make sure the server is running. Returns True if ready."""
    sock_path = _socket_path()

    # Already running and socket exists?
    if sock_path.exists() and _server_alive():
        return True

    # Start it
    if not _start_server():
        return False

    # Wait for socket to appear
    deadline = time.monotonic() + _CONNECT_TIMEOUT
    while time.monotonic() < deadline:
        if sock_path.exists() and _server_alive():
            return True
        time.sleep(0.05)

    return False


def try_generate(
    text: str, voice: str, speed: float, model_id: str
) -> tuple[np.ndarray, int] | None:
    """Try to generate audio via the background server.

    Returns (samples, sample_rate) on success, or None if the server
    is unavailable (caller should fall back to direct generation).
    """
    if not ensure_server():
        return None

    sock_path = _socket_path()

    try:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(_REQUEST_TIMEOUT)
        conn.connect(str(sock_path))

        # Send request
        req = json.dumps({
            "text": text,
            "voice": voice,
            "speed": speed,
            "model": model_id,
        }).encode() + b"\n"
        conn.sendall(req)

        # Read response header: [4B sample_rate][4B data_len]
        header = _recv_exact(conn, 8)
        if header is None:
            return None

        sample_rate, data_len = struct.unpack("<II", header)

        # Read payload
        payload = _recv_exact(conn, data_len)
        if payload is None:
            return None

        conn.close()

        # sample_rate == 0 means error
        if sample_rate == 0:
            error_msg = payload.decode(errors="replace")
            print(f"sag server error: {error_msg}", file=sys.stderr)
            return None

        samples = np.frombuffer(payload, dtype=np.float32)
        return samples, sample_rate

    except (ConnectionError, OSError, socket.timeout) as exc:
        print(f"sag server: connection failed ({exc}), using direct mode", file=sys.stderr)
        return None


def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
    """Receive exactly n bytes from socket."""
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data
