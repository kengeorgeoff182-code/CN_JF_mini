# Frontend — D1 Multi-Client Chat

This directory adds a browser-based user interface on top of the existing TCP chat application.

## Design

The browser does **not** replace the low-level TCP client/server implementation used for D1. Instead, `web_app.py` acts as a small frontend gateway:

```text
Browser UI
    |
    | HTTP / JSON
    v
Frontend Gateway
    |
    | TCP socket
    v
Chat Server
```

The gateway maintains one TCP connection to the chat server for each browser session. Messages received from the TCP server are exposed to the browser through a small polling API.

## Run

Start the existing chat server first:

```bash
python3 server/server.py
```

In another terminal:

```bash
python3 frontend/web_app.py
```

Open:

```text
http://127.0.0.1:8080
```

The default chat server is `127.0.0.1:5000`. For another server address, enter it in the frontend before connecting.

## Mininet use

For a Mininet demonstration, the TCP client and server continue to run inside the Mininet hosts. The browser gateway can be pointed at the chat server's reachable address when the environment provides a route from the browser host to the Mininet service.

The existing terminal client remains available for D1 socket-level testing and should not be removed.
