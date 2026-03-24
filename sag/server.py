"""Background TTS model server.

Keeps the ONNX model loaded in memory and serves generation requests
over a Unix domain socket. Auto-exits after an idle timeout.

Protocol:
  Request:  JSON line: {"text":..., "voice":..., "speed":..., "model":...}\n
  Response: [4B sample_rate LE][4B data_len LE][data_len bytes float32 PCM]
  Error:    [4B zero][4B msg_len LE][msg_len bytes UTF-8 error message]
"""

from __future__ import annotations

import json
import os
import signal
import socket
import struct
import sys
import threading
import time
from pathlib import Path

import numpy as np

SOCK_DIR = Path("/tmp")
IDLE_TIMEOUT = 60  # seconds


def _socket_path() -> Path:
    return SOCK_DIR / f"sag-{os.getuid()}.sock"


def _pid_path() -> Path:
    return SOCK_DIR / f"sag-{os.getuid()}.pid"


class ModelServer:
    """Single-threaded TTS server on a Unix socket with idle auto-exit."""

    def __init__(self, idle_timeout: int = IDLE_TIMEOUT):
        self.idle_timeout = idle_timeout
        self.sock_path = _socket_path()
        self.pid_path = _pid_path()
        self._last_activity = time.monotonic()
        self._shutdown = threading.Event()
        self._server_sock: socket.socket | None = None

    def run(self) -> None:
        """Start serving. Blocks until idle timeout or signal."""
        self._cleanup_stale()
        self._write_pid()

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Create and bind socket
        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._server_sock.bind(str(self.sock_path))
            os.chmod(str(self.sock_path), 0o600)
            self._server_sock.listen(4)
            self._server_sock.settimeout(1.0)  # poll interval

            print(f"sag server started (pid={os.getpid()}, timeout={self.idle_timeout}s)", file=sys.stderr)

            # Start idle watchdog
            watchdog = threading.Thread(target=self._idle_watchdog, daemon=True)
            watchdog.start()

            while not self._shutdown.is_set():
                try:
                    conn, _ = self._server_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                self._last_activity = time.monotonic()
                try:
                    self._handle_connection(conn)
                except Exception as exc:
                    print(f"sag server: error handling request: {exc}", file=sys.stderr)
                finally:
                    conn.close()
                    self._last_activity = time.monotonic()

        finally:
            self._cleanup()

    def _handle_connection(self, conn: socket.socket) -> None:
        """Read one request, generate audio, send response."""
        # Read JSON line
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk

        try:
            req = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error(conn, f"Invalid request: {exc}")
            return

        text = req.get("text", "")
        voice = req.get("voice", "Bella")
        speed = req.get("speed", 1.0)
        model_id = req.get("model", "")

        if not text:
            self._send_error(conn, "Empty text")
            return

        try:
            from sag.tts import generate

            samples, sample_rate = generate(text, voice, speed, model_id)
            self._send_audio(conn, samples, sample_rate)
        except Exception as exc:
            self._send_error(conn, str(exc))

    def _send_audio(self, conn: socket.socket, samples: np.ndarray, sample_rate: int) -> None:
        """Send binary audio response."""
        audio_bytes = samples.astype(np.float32).tobytes()
        header = struct.pack("<II", sample_rate, len(audio_bytes))
        conn.sendall(header + audio_bytes)

    def _send_error(self, conn: socket.socket, message: str) -> None:
        """Send error response (sample_rate=0 signals error)."""
        msg_bytes = message.encode()
        header = struct.pack("<II", 0, len(msg_bytes))
        conn.sendall(header + msg_bytes)

    def _idle_watchdog(self) -> None:
        """Exit if no activity for idle_timeout seconds."""
        while not self._shutdown.is_set():
            elapsed = time.monotonic() - self._last_activity
            if elapsed >= self.idle_timeout:
                print(f"sag server: idle for {self.idle_timeout}s, shutting down", file=sys.stderr)
                self._shutdown.set()
                # Wake up the accept() loop
                if self._server_sock:
                    try:
                        self._server_sock.close()
                    except OSError:
                        pass
                return
            time.sleep(1)

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle SIGTERM/SIGINT."""
        self._shutdown.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass

    def _cleanup_stale(self) -> None:
        """Remove stale socket/pid from a previous crashed server."""
        if self.pid_path.exists():
            try:
                old_pid = int(self.pid_path.read_text().strip())
                os.kill(old_pid, 0)
                # Process still alive — another server is running
                print(f"sag server: another instance running (pid={old_pid})", file=sys.stderr)
                sys.exit(1)
            except (ProcessLookupError, ValueError):
                pass  # stale, clean up
            except PermissionError:
                # Process exists but we can't signal it
                print("sag server: another instance may be running", file=sys.stderr)
                sys.exit(1)

        # Remove stale files
        self.sock_path.unlink(missing_ok=True)
        self.pid_path.unlink(missing_ok=True)

    def _write_pid(self) -> None:
        self.pid_path.write_text(str(os.getpid()))

    def _cleanup(self) -> None:
        """Remove socket and pid file."""
        self.sock_path.unlink(missing_ok=True)
        self.pid_path.unlink(missing_ok=True)
        print("sag server: stopped", file=sys.stderr)


def run_server(idle_timeout: int = IDLE_TIMEOUT) -> None:
    """Entry point for the background server."""
    server = ModelServer(idle_timeout=idle_timeout)
    server.run()
