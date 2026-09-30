# Phase 2 setup

## Controller dependency

This phase uses **OS-Ken**, the maintained OpenStack fork of Ryu. Install it in the controller Python environment.

The current OS-Ken package requires Python >= 3.10 and publishes classifiers through Python 3.13.

Example:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install os-ken
```

Mininet and Open vSwitch must be installed in the Linux/WSL environment used for the network lab.

## Start the controller

From the project root:

```bash
source .venv/bin/activate
python sdn/run_controller.py
```

The controller is configured for OpenFlow 1.3 and TCP chat port 5000.

## Start Mininet

In a second terminal:

```bash
sudo python3 mininet/topology.py
```

Inside the Mininet CLI:

```text
h3 python3 server/server.py
```

Then from other Mininet terminals:

```text
xterm h1 h2
```

or use the Mininet CLI with shell commands.

Example client commands from h1 and h2:

```text
h1 python3 client/client.py --host 10.0.0.3 --port 5000
h2 python3 client/client.py --host 10.0.0.3 --port 5000
```

## D1 evidence to capture

1. controller shows switch connection;
2. `pingall` succeeds;
3. chat server listens on h3:5000;
4. h1 and h2 establish TCP connections to h3;
5. chat messages are exchanged;
6. controller log shows `[CHAT-TRAFFIC]` entries for TCP port 5000.
