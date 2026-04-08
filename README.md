# Project 14: Link Failure Detection and Recovery

**Course**: Computer Networks — UE24CS252B  
**Controller**: POX (OpenFlow 1.0)  
**Topology**: Triangle (3 switches, 2 hosts)

---

## Problem Statement

Implement an SDN-based system using Mininet and POX controller that:
- Monitors network topology for link/port failures
- Detects when a switch port goes down
- Automatically flushes stale flow rules from affected switches
- Restores end-to-end connectivity through an alternate backup path
- Logs all events clearly for demonstration

---

## Topology
H1 (10.0.0.1)
|
S1 ────── S2
\        /
\      /
S3───
|
H2 (10.0.0.2)

**Primary path**: H1 → S1 → S2 → S3 → H2  
**Backup path**: H1 → S1 → S3 → H2 (used when S1-S2 link fails)

---

## SDN Logic and Flow Rule Design

### Controller Events Handled

| Event | Handler | Action |
|---|---|---|
| Switch connects | `_handle_ConnectionUp` | Install table-miss rule |
| Packet arrives | `_handle_PacketIn` | Learn MAC, install unicast flow |
| Port goes down | `_handle_PortStatus` | Flush flows, clear MAC table |
| Port comes up | `_handle_PortStatus` | Log restoration |

### Match-Action Rule Design

- **Table-miss rule**: priority=0, match=ALL, action=CONTROLLER
- **Unicast rule**: priority=10, match=in_port+eth_dst, action=OUTPUT(port), idle_timeout=30, hard_timeout=120

### Link Failure Recovery Logic

1. `port_status` event fires with reason=DELETE
2. Controller calls `_flush_flows()` — deletes all rules on that switch
3. Controller clears MAC address table for that switch
4. Next packets flood through all available ports
5. Traffic automatically re-routes via backup path S1→S3
6. New flow rules installed along backup path

---

## Setup

### Prerequisites
```bash
sudo apt install mininet -y
sudo apt install python3 -y
git clone https://github.com/noxrepo/pox.git
```

### Clone this repository
```bash
git clone https://github.com/<your-username>/sdn-project14-link-failure.git
cd sdn-project14-link-failure
cp link_failure.py pox/ext/
```

---

## How to Run

Open **2 terminals**.

**Terminal 1 — Start POX controller:**
```bash
cd pox
python3 pox.py openflow.of_01 link_failure
```

Wait for:
[INFO] Controller ready. Waiting for switches...

**Terminal 2 — Start Mininet topology:**
```bash
sudo mn --custom topology.py --topo triangle \
  --controller remote,ip=127.0.0.1,port=6633 \
  --switch ovsk --mac
```

---

## Test Scenarios

### Scenario 1 — Normal Operation
```bash
mininet> pingall
```
Expected: 0% packet loss
```bash
mininet> h1 ping -c 5 h2
```
Expected: 0% loss, ~1ms RTT
```bash
mininet> iperf h1 h2
```
Expected: throughput measuremen

### Scenario 2 — Link Failure and Recovery
Step 1: Confirm normal connectivity
mininet> h1 ping -c 3 h2

Step 2: Simulate link failure
mininet> link s1 s2 down

Step 3: Traffic reroutes via S1-S3 backup path

mininet> h1 ping -c 5 h2

Step 4: Check flow tables changed(in Terminal 3)

sudo ovs-ofctl dump-flows s1

sudo ovs-ofctl dump-flows s2

sudo ovs-ofctl dump-flows s3

Step 5: Restore link

mininet> link s1 s2 up

Step 6: Confirm full recovery

mininet> h1 ping -c 5 h2

mininet> iperf h1 h2

## Expected Controller Output
[HH:MM:SS] --- [INFO] Controller ready. Waiting for switches...
[HH:MM:SS] --- [INFO] Switch 00-00-00-00-00-01 connected.
[HH:MM:SS] --- [INFO] Switch 00-00-00-00-00-02 connected.
[HH:MM:SS] --- [INFO] Switch 00-00-00-00-00-03 connected.
[HH:MM:SS] --- [INFO] s1: Learned 00:00:00:00:00:01 on port 1
[HH:MM:SS] +++ [SUCCESS] s1: Flow installed port 1->00:00:00:00:00:02->port 2
[HH:MM:SS] !!! [WARN] LINK FAILURE on s1 port 2
[HH:MM:SS] +++ [SUCCESS] s1: Flushed. Re-routing via backup path.
[HH:MM:SS] +++ [SUCCESS] LINK RESTORED on s1 port 2

---

## Performance Observations

| Metric | Normal | After Failure | After Recovery |
|---|---|---|---|
| Ping RTT | ~1ms | brief loss then recovers | ~1ms |
| Packet Loss | 0% | 1-2 packets | 0% |
| Throughput (iperf) | X Mbps | reduced | X Mbps |
| Flow table rules | unicast rules | cleared then rebuilt | unicast rules |

*(Fill in your actual measured values from iperf and ping)*

---

## Proof of Execution

*(Add your screenshots here)*

- Screenshot 1: `pingall` — 0% packet loss (normal)
- Screenshot 2: `h1 ping h2` after `link s1 s2 down` — recovery via backup
- Screenshot 3: Flow table before link failure
- Screenshot 4: Flow table after link failure — rules cleared
- Screenshot 5: Controller logs showing WARN/SUCCESS messages
- Screenshot 6: Wireshark capture showing ICMP packets
- Screenshot 7: iperf throughput results

---

## Cleanup
```bash
mininet> exit
sudo mn -c
```

---

## References

1. POX Controller Documentation — https://noxrepo.github.io/pox-doc/html/
2. Mininet Walkthrough — https://mininet.org/walkthrough/
3. OpenFlow 1.0 Specification — https://opennetworking.org
4. OVS OpenFlow — https://docs.openvswitch.org
5. Mininet Documentation — https://github.com/mininet/mininet/wiki/Documentation
