"""
Project 14: Link Failure Detection and Recovery
Triangle topology — 3 switches, 2 hosts, 2 paths
"""
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class TriangleTopo(Topo):
    def build(self):
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        self.addLink(h1, s1)
        self.addLink(h2, s3)

        self.addLink(s1, s2)   # primary path segment
        self.addLink(s2, s3)   # primary path segment
        self.addLink(s1, s3)   # backup path (direct)


topos = {'triangle': TriangleTopo}


def run():
    setLogLevel('info')
    topo = TriangleTopo()

    net = Mininet(
        topo=topo,
        controller=RemoteController('c0', ip='127.0.0.1', port=6633),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True  # reduces ARP-related initial loss
    )

    net.start()

    # IMPORTANT for triangle: prevent flooding loops by enabling STP
    for s in net.switches:
        s.cmd('ovs-vsctl set Bridge %s stp_enable=true' % s.name)

    info('\n*** H1=10.0.0.1  H2=10.0.0.2\n')
    info('*** Triangle: S1-S2-S3, backup path S1-S3\n')
    info('*** STP enabled on all switches to prevent L2 flood loops\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()