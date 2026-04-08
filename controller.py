from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.revent import EventMixin
import pox.openflow.libopenflow_01 as of
import datetime

log = core.getLogger()

def logp(tag, msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    sym = {'INFO': '---', 'WARN': '!!!', 'SUCCESS': '+++'}
    print(f"[{ts}] {sym.get(tag, '---')} [{tag}] {msg}", flush=True)


class SwitchController(EventMixin):
    """
    Learning switch with:
    - Table-miss -> controller (no buffering)
    - MAC learning
    - Flow install using buffer_id when available
    - On port delete: flush flows + clear MAC table (forces re-learn on new path)
    """

    def __init__(self, connection, dpid):
        self.connection = connection
        self.dpid = dpid
        self.mac_to_port = {}  # {EthAddr -> port_no}

        connection.addListeners(self)
        logp('INFO', f'Switch {dpid_to_str(dpid)} connected.')
        self._install_table_miss()

    def _install_table_miss(self):
        fm = of.ofp_flow_mod()
        fm.priority = 0
        fm.match = of.ofp_match()  # match all
        # Send full packet to controller (avoid OVS buffering weirdness)
        fm.actions.append(of.ofp_action_output(
            port=of.OFPP_CONTROLLER,
            max_len=of.OFPCML_NO_BUFFER
        ))
        self.connection.send(fm)

    def _flush_flows(self):
        fm = of.ofp_flow_mod()
        fm.command = of.OFPFC_DELETE
        fm.out_port = of.OFPP_NONE
        fm.match = of.ofp_match()  # delete all
        self.connection.send(fm)
        self._install_table_miss()
        logp('INFO', f's{self.dpid}: Flow table flushed.')

    def _handle_PacketIn(self, event):
        packet = event.parsed
        inport = event.port

        if packet is None or not packet.parsed:
            return

        src_mac = packet.src
        dst_mac = packet.dst

        # Learn / update source MAC -> port
        old = self.mac_to_port.get(src_mac)
        if old is None:
            self.mac_to_port[src_mac] = inport
            logp('INFO', f's{self.dpid}: Learned {src_mac} on port {inport}')
        elif old != inport:
            # In real networks MAC moves happen; update.
            logp('WARN', f's{self.dpid}: MAC {src_mac} moved {old} -> {inport}')
            self.mac_to_port[src_mac] = inport

        # Forwarding decision
        out_port = self.mac_to_port.get(dst_mac)

        if out_port is None:
            # Unknown dst: flood (STP in Mininet will prevent loop storms)
            po = of.ofp_packet_out()
            po.in_port = inport
            po.data = event.ofp
            po.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            self.connection.send(po)
            logp('INFO', f's{self.dpid}: Flooded for unknown {dst_mac}')
            return

        # Known dst: don't send back out same port
        if out_port == inport:
            return

        # Install flow for this direction
        fm = of.ofp_flow_mod()
        fm.priority = 10
        fm.idle_timeout = 30
        fm.hard_timeout = 120
        fm.match = of.ofp_match(in_port=inport, dl_dst=dst_mac)
        fm.actions.append(of.ofp_action_output(port=out_port))

        # IMPORTANT: use buffer_id when switch buffered the packet
        # (even though we set NO_BUFFER in table-miss, keep this correct anyway)
        if hasattr(event.ofp, "buffer_id") and event.ofp.buffer_id not in (None, -1):
            fm.buffer_id = event.ofp.buffer_id
        else:
            fm.data = event.ofp

        self.connection.send(fm)
        logp('SUCCESS', f's{self.dpid}: Flow {inport}->{dst_mac}->port {out_port}')

    def _handle_PortStatus(self, event):
        # Some OVS setups report link down as PORT_STATUS with reason=DELETE.
        port = event.ofp.desc.port_no
        reason = event.ofp.reason

        if reason == of.OFPPR_DELETE:
            logp('WARN', f'LINK FAILURE on s{self.dpid} port {port}')
            self.mac_to_port.clear()
            self._flush_flows()
            logp('SUCCESS', f's{self.dpid}: Cleared MAC table and flushed flows (re-learn).')
        elif reason == of.OFPPR_ADD:
            logp('SUCCESS', f'LINK RESTORED on s{self.dpid} port {port}')
        else:
            # MODIFY or other
            logp('INFO', f's{self.dpid}: PortStatus reason={reason} port={port}')


class LinkFailureController(EventMixin):
    def __init__(self):
        core.openflow.addListeners(self)
        logp('INFO', 'Controller ready. Waiting for switches...')

    def _handle_ConnectionUp(self, event):
        SwitchController(event.connection, event.dpid)


def launch():
    core.registerNew(LinkFailureController)