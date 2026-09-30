# Phase 2 — Mininet + SDN

## Goal

Place the Phase 1 TCP chat application inside a controlled Mininet topology and connect the Open vSwitch switch to an OpenFlow 1.3 SDN controller.

## Topology

```text
h1 (client) \
             \
              s1 (Open vSwitch) ---- controller (OpenFlow 1.3)
             /
 h2 (client) /
            \
             h3 (chat server)
```

Hosts:

- h1: 10.0.0.1/24
- h2: 10.0.0.2/24
- h3: 10.0.0.3/24
- Chat TCP port: 5000

## D1 controller behavior

The controller currently performs three things:

1. installs a table-miss rule that sends unknown packets to the controller;
2. learns MAC addresses and installs forwarding flows;
3. identifies IPv4/TCP traffic belonging to the chat service and logs it as `[CHAT-TRAFFIC]` while installing a higher-priority learned flow.

This is deliberately **D1 scope**. QoS, congestion response, rerouting, load balancing and other dynamic policy mechanisms are reserved for D2.

## Why this counts as socket-SDN integration

The TCP chat server and clients execute as Mininet hosts. Their packets cross the Open vSwitch/SDN data plane. The controller receives the corresponding OpenFlow events, classifies TCP port 5000 as chat traffic, and programs forwarding behavior.
