#!/usr/bin/env python3
"""Browser frontend gateway for the TCP chat server.

The browser talks HTTP/JSON to this gateway. The gateway maintains one raw TCP
socket to the chat server per browser session, so the core chat protocol remains
TCP-based and is unchanged.
"""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
MAX_MESSAGES = 500
BUFFER_SIZE = 4096


@dataclass
class Session:
    session_id: str
    sock: socket.socket
    username: str
    messages: list[tuple[int, str]] = field(default_factory=list)
    next_seq: int = 1
    lock: threading.Lock = field(default_factory=threading.Lock)
    receiver: threading.Thread | None = None
    closed: bool = False

    def add_message(self, message: str) -> None:
        with self.lock:
            self.messages.append((self.next_seq, message))
            self.next_seq += 1
            if len(self.messages) > MAX_MESSAGES:
                del self.messages[: len(self.messages) - MAX_MESSAGES]

    def get_messages_after(self, after: int) -> list[dict[str, Any]]:
        with self.lock:
            return [
                {"seq": seq, "message": message}
                for seq, message in self.messages
                if seq > after
            ]


sessions: dict[str, Session] = {}
sessions_lock = threading.Lock()


def send_line(sock: socket.socket, message: str) -> None:
    sock.sendall((message + "\n").encode("utf-8"))


def receive_first_line(sock: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("Server closed before sending a welcome message.")
        if chunk == b"\n":
            return b"".join(chunks).decode("utf-8")
        chunks.append(chunk)


def receiver_loop(session: Session) -> None:
    file = session.sock.makefile("r", encoding="utf-8", newline="\n")
    try:
        while True:
            line = file.readline()
            if not line:
                session.add_message("INFO|Server disconnected.")
                break
            session.add_message(line.rstrip("\n"))
    except (ConnectionError, OSError, UnicodeDecodeError) as exc:
        session.add_message(f"ERROR|Receive failed: {exc}")
    finally:
        try:
            file.close()
        except OSError:
            pass
        with session.lock:
            session.closed = True


def create_session(username: str, server_host: str, server_port: int) -> tuple[Session, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        sock.connect((server_host, server_port))
        welcome = receive_first_line(sock)
        send_line(sock, username)
        sock.settimeout(None)
    except Exception:
        sock.close()
        raise

    session = Session(
        session_id=secrets.token_urlsafe(18),
        sock=sock,
        username=username,
    )
    session.add_message(welcome)

    receiver = threading.Thread(target=receiver_loop, args=(session,), daemon=True)
    session.receiver = receiver
    receiver.start()

    with sessions_lock:
        sessions[session.session_id] = session

    return session, session.session_id


def get_session(session_id: str) -> Session | None:
    with sessions_lock:
        return sessions.get(session_id)


def close_session(session: Session) -> None:
    with session.lock:
        already_closed = session.closed
        session.closed = True

    if not already_closed:
        try:
            send_line(session.sock, "/quit")
        except OSError:
            pass

    try:
        session.sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        session.sock.close()
    except OSError:
        pass

    with sessions_lock:
        sessions.pop(session.session_id, None)


def json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0 or content_length > 64 * 1024:
        raise ValueError("Invalid request body")
    raw = handler.rfile.read(content_length)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


class FrontendHandler(BaseHTTPRequestHandler):
    server_version = "D1ChatFrontend/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[WEB] {self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            try:
                body = INDEX_FILE.read_bytes()
            except OSError:
                json_response(self, {"error": "Frontend file unavailable."}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/health":
            json_response(self, {"status": "ok"})
            return

        if parsed.path == "/api/messages":
            query = parse_qs(parsed.query)
            session_id = query.get("session", [""])[0]
            try:
                after = int(query.get("after", ["0"])[0])
            except ValueError:
                after = 0
            session = get_session(session_id)
            if session is None:
                json_response(self, {"error": "Unknown session."}, HTTPStatus.NOT_FOUND)
                return
            with session.lock:
                closed = session.closed
                username = session.username
            json_response(self, {
                "messages": session.get_messages_after(after),
                "closed": closed,
                "username": username,
            })
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            data = read_json(self)
        except (ValueError, json.JSONDecodeError) as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        try:
            if parsed.path == "/api/connect":
                username = str(data.get("username", "")).strip()
                server_host = str(data.get("server_host", "127.0.0.1")).strip()
                server_port = int(data.get("server_port", 5000))

                if not username:
                    raise ValueError("Username cannot be empty.")
                if len(username) > 32:
                    raise ValueError("Username is too long.")
                if not (1 <= server_port <= 65535):
                    raise ValueError("Invalid server port.")

                session, session_id = create_session(username, server_host, server_port)
                json_response(self, {
                    "session": session_id,
                    "username": username,
                    "message": "Connected to chat server.",
                })
                return

            if parsed.path == "/api/send":
                session = get_session(str(data.get("session", "")))
                message = str(data.get("message", "")).strip()
                if session is None:
                    json_response(self, {"error": "Unknown session."}, HTTPStatus.NOT_FOUND)
                    return
                if not message:
                    raise ValueError("Message cannot be empty.")
                if len(message) > 1000:
                    raise ValueError("Message is too long.")
                try:
                    send_line(session.sock, message)
                except OSError as exc:
                    session.add_message(f"ERROR|Send failed: {exc}")
                    json_response(self, {"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
                    return
                json_response(self, {"sent": True})
                return

            if parsed.path == "/api/disconnect":
                session = get_session(str(data.get("session", "")))
                if session is not None:
                    close_session(session)
                json_response(self, {"disconnected": True})
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (ConnectionError, OSError) as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D1 browser frontend gateway")
    parser.add_argument("--web-host", default="127.0.0.1")
    parser.add_argument("--web-port", type=int, default=8080)
    parser.add_argument("--server-host", default="127.0.0.1")
    parser.add_argument("--server-port", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # These defaults are displayed in the UI; each session may override them.
    print("=" * 64)
    print("D1 Chat Frontend Gateway")
    print(f"Web UI: http://{args.web_host}:{args.web_port}")
    print(f"Default chat server: {args.server_host}:{args.server_port}")
    print("Press Ctrl+C to stop the frontend.")
    print("=" * 64)
    httpd = ThreadingHTTPServer((args.web_host, args.web_port), FrontendHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Frontend stopped.")
    finally:
        httpd.server_close()
        with sessions_lock:
            active = list(sessions.values())
        for session in active:
            close_session(session)


if __name__ == "__main__":
    main()
