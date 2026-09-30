import socket
import threading
from typing import Dict, Tuple

HOST = "0.0.0.0"
PORT = 5000
BACKLOG = 50
BUFFER_SIZE = 4096

clients: Dict[socket.socket, str] = {}
clients_lock = threading.Lock()


def send_line(conn: socket.socket, message: str) -> None:
    """Send one newline-delimited application message."""
    data = (message + "\n").encode("utf-8")
    conn.sendall(data)


def broadcast(message: str, exclude: socket.socket | None = None) -> None:
    """Send a message to every connected client except `exclude`."""
    with clients_lock:
        recipients = list(clients.keys())

    dead_connections = []

    for conn in recipients:
        if conn is exclude:
            continue

        try:
            send_line(conn, message)
        except (ConnectionError, OSError):
            dead_connections.append(conn)

    for conn in dead_connections:
        remove_client(conn)


def remove_client(conn: socket.socket) -> str | None:
    """Remove a client from the registry and close its socket."""
    with clients_lock:
        username = clients.pop(conn, None)

    try:
        conn.close()
    except OSError:
        pass

    return username


def handle_client(conn: socket.socket, address: Tuple[str, int]) -> None:
    """Handle one client's complete TCP session."""
    username = None

    try:
        send_line(conn, "WELCOME|Enter your username:")

        file = conn.makefile("r", encoding="utf-8", newline="\n")

        first_line = file.readline()
        if not first_line:
            return

        username = first_line.strip()
        if not username:
            send_line(conn, "ERROR|Username cannot be empty.")
            return

        with clients_lock:
            existing_names = set(clients.values())
            if username in existing_names:
                send_line(conn, "ERROR|Username already in use.")
                return
            clients[conn] = username

        send_line(conn, f"INFO|Registered as {username}.")
        send_line(conn, "INFO|Type messages and press Enter. Type /quit to disconnect.")
        broadcast(f"SYSTEM|{username} joined the chat.", exclude=conn)

        print(f"[CONNECT] {username} from {address}")

        while True:
            line = file.readline()
            if not line:
                break

            message = line.strip()
            if not message:
                continue

            if message == "/quit":
                break

            chat_message = f"MSG|{username}|{message}"
            print(f"[MESSAGE] {chat_message}")
            broadcast(chat_message, exclude=conn)
            send_line(conn, f"INFO|Sent: {message}")

    except (ConnectionError, OSError, UnicodeDecodeError) as exc:
        print(f"[ERROR] Client {address}: {exc}")
    finally:
        removed_username = remove_client(conn)
        if removed_username:
            print(f"[DISCONNECT] {removed_username} from {address}")
            broadcast(f"SYSTEM|{removed_username} left the chat.")


def main() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(BACKLOG)

        print("=" * 60)
        print("Multi-Client TCP Chat Server")
        print(f"Listening on {HOST}:{PORT}")
        print("Press Ctrl+C to stop the server.")
        print("=" * 60)

        try:
            while True:
                conn, address = server_socket.accept()
                thread = threading.Thread(
                    target=handle_client,
                    args=(conn, address),
                    daemon=True,
                )
                thread.start()
                print(f"[THREAD] Started handler for {address}")
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Server stopped.")


if __name__ == "__main__":
    main()
