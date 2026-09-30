# Phase 2 test plan

| Test | Action | Expected result |
|---|---|---|
| T1 | Start controller, then Mininet | Switch connects to controller |
| T2 | Run `pingall` | All 3 hosts can reach one another |
| T3 | Start chat server on h3 | Server listens on TCP/5000 |
| T4 | Connect h1 and h2 to h3 | Both TCP sessions succeed simultaneously |
| T5 | Send chat message from h1 | h2 receives the broadcast |
| T6 | Observe controller | `[CHAT-TRAFFIC]` appears for TCP/5000 |
| T7 | Stop one client | Server and other client continue operating |
