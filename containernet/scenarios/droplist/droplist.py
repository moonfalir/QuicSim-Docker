#!/usr/bin/python
from mininet.net import Containernet
from mininet.node import POX
from mininet.cli import CLI
from mininet.link import TCLink, Intf
from mininet.log import info, setLogLevel
from os import environ
from argparse import ArgumentParser
from time import sleep

class Droplist:
    def addCLIArguments(self, p2p_parser):
        p2p_parser.add_argument('--delay', action='store', type=str, required=True, help='One-way delay of network, specify with units.')
        p2p_parser.add_argument('--bandwidth', action='store', type=float, required=True, help='Bandwidth of the link in Mbit/s.')
        p2p_parser.add_argument('--queue', action='store', type=int, required=True, help='Queue size of the queue attached to the link. Specified in packets.')
        p2p_parser.add_argument('--drops_to_client', action='store', type=str, required=False, help="Index of UDP packets send to the client that need to be dropped")
        p2p_parser.add_argument('--drops_to_server', action='store', type=str, required=False, help="Index of UDP packets send to the server that need to be dropped")

    def run(self, sim_args):
        if any(v not in environ for v in ['CLIENT', 'CLIENT_PARAMS', 'SERVER', 'SERVER', 'LOGDIR']):
            # TODO show help
            exit(1)
        client_image = environ['CLIENT']
        client_command = environ['CLIENT_PARAMS']
        server_image = environ['SERVER']
        server_command = environ['SERVER_PARAMS']
        logdir = environ['LOGDIR']

        setLogLevel('info')

        net = Containernet(controller=POX)
        info('*** Adding controller\n')
        poxCommand = 'forwarding.droplist'
        
        if sim_args.drops_to_client != None:
            poxCommand += ' --droplist_server=' + sim_args.drops_to_client

        if sim_args.drops_to_server != None:
            poxCommand += ' --droplist_client=' + sim_args.drops_to_server
        
        net.addController('c0', poxArgs = poxCommand)
        info('*** Adding docker containers\n')
        server = net.addDocker('server', ip='10.0.0.251',
                               dimage=server_image + ":latest",
                               dcmd=server_command,
                               volumes=[logdir + '/logs/server:/logs'])
        client = net.addDocker('client', ip='10.0.0.252', 
                               dimage=client_image + ":latest", 
                               volumes=[logdir + '/logs/client:/logs'])
        info('*** Adding switch\n')
        s1 = net.addSwitch('s1')
        info('*** Creating links\n')
        net.addLink(server, s1, cls=TCLink, delay=sim_args.delay, bw=sim_args.bandwidth, max_queue_size=sim_args.queue)
        net.addLink(client, s1, cls=TCLink)
        info('*** Starting network\n')
        net.start()
        info('\n' + client_command + '\n')
        info(client.cmd(client_command) + "\n")
        # Wait some time to allow server finish writing to log file
        sleep(3)
        info('*** Stopping network')
        net.stop()