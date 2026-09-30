import argparse
import socket
import threading

DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 5000


def receive_messages(sock: socket.socket) -> None:
    """Continuously receive newline-delimited messages from the server."""
    file = sock.makefile("r", encoding="utf-8", newline="\n")

    try:
        while True:
            line = file.readline()
            if not line:
                print("\n[INFO] Server disconnected.")
                break

            message = line.rstrip("\n")
            print(f"\n{message}")
            print("> ", end="", flush=True)
    except (ConnectionError, OSError, UnicodeDecodeError) as exc:
        print(f"\n[ERROR] Receive failed: {exc}")
    finally:
        try:
            file.close()
        except OSError:
            pass


def receive_first_line(sock: socket.socket) -> str:
    """Read exactly one line before handing the socket to the receiver thread."""
    chunks = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("Server closed before sending a welcome message.")
        if chunk == b"\n":
            return b"".join(chunks).decode("utf-8")
        chunks.append(chunk)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TCP chat client")
    parser.add_argument(
        "--host",
        default=DEFAULT_SERVER_HOST,
        help="Chat server IP/hostname (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help="Chat server TCP port (default: 5000)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    username = input("Enter username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((args.host, args.port))
        except OSError as exc:
            print(f"Could not connect to {args.host}:{args.port}: {exc}")
            return

        print(receive_first_line(sock))
        sock.sendall((username + "\n").encode("utf-8"))

        receiver = threading.Thread(
            target=receive_messages,
            args=(sock,),
            daemon=True,
        )
        receiver.start()

        print(f"[INFO] Connected to {args.host}:{args.port}")

        try:
            while True:
                message = input("> ").strip()
                if not message:
                    continue

                try:
                    sock.sendall((message + "\n").encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError, OSError):
                    print("\n[ERROR] Connection to server is no longer available.")
                    break

                if message == "/quit":
                    break
        except (KeyboardInterrupt, EOFError):
            try:
                sock.sendall(b"/quit\n")
            except OSError:
                pass
        finally:
            receiver.join(timeout=1.0)
            print("[INFO] Client stopped.")


if __name__ == "__main__":
    main()
