"""D1 Mininet topology: two clients, one chat server, one OpenFlow switch."""

from mininet.cli import CLI
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo


class ChatTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        h3 = self.addHost("h3", ip="10.0.0.3/24")

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)


def run():
    net = Mininet(
        topo=ChatTopo(),
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    controller = RemoteController("c0", ip="127.0.0.1", port=6653)
    net.addController(controller)

    info("*** Starting network\n")
    net.start()

    info("*** Testing host reachability\n")
    net.pingAll()

    info("*** D1 topology ready\n")
    info("*** Server host: h3\n")
    info("*** Client hosts: h1, h2\n")
    info("*** Chat server TCP port: 5000\n")
    info("*** Start server inside h3 and clients inside h1/h2\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
