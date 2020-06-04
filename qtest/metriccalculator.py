import os, json

class MetricCalculator():
    _metricsperfile = []
    _json_columns = ['name', 'sim', 'mdn_goodput', 'mdn_throughput', 'mdn_rtt', 'mdn_cwnd']
    
    def calculateMetrics(self, logdir: str, tcpdumpfiles: list, qlogfile: str, istcpdump: bool, isquic: bool, sim: str, run: int):
        split_dir = logdir.split("/")
        name = split_dir[len(split_dir) - 3] + "/" + split_dir[len(split_dir) - 2]

        totals = {
            "rtt_amount": 0,
            "tp_time": 0,
            "gp_time": 0,
            "cwnd_amount": 0,
            "unacked_packets": {}
        }
        run_avgs = {
            "avg_goodput": 0.0,
            "avg_throughput": 0.0,
            "avg_rtt": 0.0,
            "avg_cwnd": 0.0
        }
        for file in tcpdumpfiles:
            serverside = "server" in file
            totals, run_avgs = self.getTcpDumpMetrics(file, isquic, serverside, run_avgs, totals)
        if qlogfile != "":
            run_avgs = self.getAvgCWND(qlogfile, run_avgs, totals)

        # calculate averages
        try:
            run_avgs["avg_throughput"] /= 125.0
            run_avgs["avg_throughput"] /= totals["tp_time"]
            run_avgs["avg_goodput"] /= 125.0
            run_avgs["avg_goodput"] /= totals["gp_time"]
            run_avgs["avg_rtt"] /= totals["rtt_amount"]
            run_avgs["avg_cwnd"] /= totals["cwnd_amount"]
        except ZeroDivisionError as z:
            print()
        id = next((index for (index, d) in enumerate(self._metricsperfile) if d["name"] == name and d["sim"] == sim), None)
        if id == None:
            self._metricsperfile.append({
                "name": name,
                "sim": sim,
                "mdn_goodput": 0.0,
                "mdn_throughput": 0.0,
                "mdn_rtt": 0.0,
                "mdn_cwnd": 0.0,
                "runs": []
            })
            id = len(self._metricsperfile) - 1
        self._metricsperfile[id]["runs"].append(run_avgs)

    def getAvgCWND(self, file: str, run_avgs: dict, totals: dict):
        data = ""
        with open(file, "r") as qlog_file:
            data = qlog_file.read()

        qlog = json.loads(data)
        events = qlog["traces"][0]["events"]
        # get structure of event fields
        event_fields = [x.lower() for x in qlog["traces"][0]["event_fields"]]
        try:
            event_type_id = event_fields.index("event_type")
        except ValueError as e:
            event_type_id = event_fields.index("event")
        data_id = event_fields.index("data")

        prev_cwnd = -1.0
        # loop through events to find CWND values
        for event in events:
            if event[event_type_id] == "metrics_updated" and "cwnd" in event[data_id]:
                cur_cwnd = float(event[data_id]["cwnd"])
                if cur_cwnd != prev_cwnd:
                    run_avgs["avg_cwnd"] += cur_cwnd
                    totals["cwnd_amount"] += 1
                    prev_cwnd = cur_cwnd

        return run_avgs
    


    def getTcpDumpMetrics(self, file: str, isquic: bool, serverside: bool, run_avgs: dict, totals: dict):
        data = ""
        with open(file, "r") as tcpdump_file:
            data = tcpdump_file.read()

        packets = json.loads(data)
        serverip = ""
        print("starting process")
        for packet in packets:
            if "quic" not in packet['_source']['layers'] and isquic:
                print("skipping because no quic layer")
                continue

            if "tcp" not in packet['_source']['layers'] and not isquic:
                print("skipping because no tcp layer")
                continue
            
            if serverip == "":
                serverip = self.getServerIp(packet, isquic)
            
            isserver = self.checkPacketSendByServer(packet, serverip)
            if isquic:
                totals, run_avgs = self.processQuicPacket(packet, serverside, run_avgs, totals, isserver)
            else:
                totals, run_avgs = self.processTcpPacket(packet, serverside, run_avgs, totals, isserver)
        return totals, run_avgs

    # find out which ip is the server (sender of data)
    def getServerIp(self, packet: dict, isquic: bool):
        if isquic:
            if packet['_source']['layers']['quic']['quic.header_form'] == "1" and packet['_source']['layers']['quic']['quic.long.packet_type'] == "0":
                return packet['_source']['layers']['ip']['ip.dst']
            else:
                return ""
        else:
            if packet['_source']['layers']['tcp']['tcp.flags_tree']['tcp.flags.syn'] == "1" and packet['_source']['layers']['tcp']['tcp.flags_tree']['tcp.flags.ack'] == "1":
                return packet['_source']['layers']['ip']['ip.dst']
            else:
                return ""
    
    # check if sender of packet is server
    def checkPacketSendByServer(self, packet: dict, serverip: str):
        return serverip == packet["_source"]["layers"]["ip"]["ip.src"]

    def processQuicPacket(self, packet: dict, serverside: bool, run_avgs: dict, totals: dict, isserver: bool):
        if serverside:
            if isserver:
                try:
                    # complete size of packet
                    bytes_amount = float(packet['_source']['layers']["frame"]["frame.len"])
                    timestamp = float(packet['_source']['layers']['frame']['frame.time_relative'])
                    totals, run_avgs = self.addThroughputBytes(run_avgs, bytes_amount, totals, timestamp)
                except KeyError as e:
                    print(e)
            #find RTT
            totals, run_avgs = self.trackRTTValuesQUIC(packet, run_avgs, totals, isserver)
            #count retransmission
        else:
            if isserver:
                try:
                    frames = packet['_source']['layers']["quic"]["quic.frame"]
                    bytes_amount = 0
                    # if quic packet contains multiple frames, go through all
                    if isinstance(frames, list):
                        for frame in frames:
                            # if stream frames contains length, get value
                            if "quic.stream.length" in frame:
                                bytes_amount += float(frame['quic.stream.length'])
                            # else calculate length by parsing data
                            else:
                                if "quic.stream_data" in frame:
                                    data = frame["quic.stream_data"].replace(':', '')
                                    bytes_amount = len(data) / 2
                    else:
                        if "quic.stream.length" in frames:
                                bytes_amount += float(frames['quic.stream.length'])
                        else:
                            if "quic.stream_data" in frames:
                                data = frames["quic.stream_data"].replace(':', '')
                                bytes_amount = len(data) / 2
                    timestamp = float(packet['_source']['layers']['frame']['frame.time_relative'])
                    totals, run_avgs = self.addGoodputBytes(run_avgs, bytes_amount, totals, timestamp)
                except KeyError as e:
                    print(e)
                except TypeError as t:
                    print(t)

        return totals, run_avgs

    def processTcpPacket(self, packet: dict, serverside: bool, run_avgs: dict, totals: dict, isserver: bool):
        if serverside:
            if isserver:
                try:
                    bytes_amount = float(packet['_source']['layers']["frame"]["frame.len"])
                    timestamp = float(packet['_source']['layers']['frame']['frame.time_relative'])
                    totals, run_avgs = self.addThroughputBytes(run_avgs, bytes_amount, totals, timestamp)
                except KeyError as e:
                    print(e)
            #find RTT
            totals, run_avgs = self.trackRTTValuesTCP(packet, run_avgs, totals, isserver)
            #count retransmission
        else:
            if isserver:
                try:
                    bytes_amount = float(packet['_source']['layers']["tcp"]["tcp.len"])
                    timestamp = float(packet['_source']['layers']['frame']['frame.time_relative'])
                    totals, run_avgs = self.addGoodputBytes(run_avgs, bytes_amount, totals, timestamp)
                except KeyError as e:
                    print(e)

        return totals, run_avgs
    def trackRTTValuesQUIC(self, packet: dict, run_avgs: dict, totals: dict, isserver: bool):
        if isserver:
            try: 
                # get quic packetnumber
                if "quic.short" in packet['_source']['layers']["quic"]:
                    pn = int(packet['_source']['layers']["quic"]["quic.short"]["quic.packet_number"])
                else:
                    pn = int(packet['_source']['layers']["quic"]["quic.packet_number"])
                timestamp = float(packet['_source']['layers']['frame']['frame.time_relative']) * 1000
                # log packetnumber timestamp to compare later with ack
                totals["unacked_packets"][pn] = timestamp
            except TypeError as t:
                print(t)
            except KeyError as e:
                print(e)
        else:
            try:
                ackframe = self.getAckFrame(packet)
                if ackframe:
                    ack_timestamp = float(packet['_source']['layers']['frame']['frame.time_relative']) * 1000
                    large_ack = int(ackframe['quic.ack.largest_acknowledged'])
                    first_range = large_ack - int(ackframe['quic.ack.first_ack_range'])
                    acked_packets = []
                    ackranges = [{
                        "high_ack": large_ack,
                        "low_ack": first_range
                    }]
                    ackranges = self.getAckRangesQUIC(ackframe, ackranges, first_range)
                    # check if unacked packet is in ack ranges, if so calculate RTT
                    for index, pn_timestamp in totals["unacked_packets"].items():
                        if self.isAcked(ackranges, index, True):
                            run_avgs["avg_rtt"] += (ack_timestamp - pn_timestamp)
                            totals["rtt_amount"] += 1
                            acked_packets.append(index)
                    for acked_packet in acked_packets:
                        del totals["unacked_packets"][acked_packet]
            except TypeError as t:
                print(t)
            except KeyError as e:
                print(e)
        return totals, run_avgs

    def trackRTTValuesTCP(self, packet: dict, run_avgs: dict, totals: dict, isserver: bool):
        if isserver:
            try: 
                pn = int(packet['_source']['layers']["tcp"]["tcp.seq"])
                timestamp = float(packet['_source']['layers']['frame']['frame.time_relative']) * 1000
                totals["unacked_packets"][pn] = timestamp
            except TypeError as t:
                print(t)
            except KeyError as e:
                print(e)
        else:
            try:
                tcppacket = packet['_source']['layers']["tcp"] 
                ack_timestamp = float(packet['_source']['layers']['frame']['frame.time_relative']) * 1000
                large_ack = int(tcppacket['tcp.ack'])
                acked_packets = []
                ackranges = [{
                    "high_ack": large_ack,
                    "low_ack": 0
                }]
                ackranges = self.getAckRangesTCP(tcppacket, ackranges)
                for index, pn_timestamp in totals["unacked_packets"].items():
                    if self.isAcked(ackranges, index, False):
                        run_avgs["avg_rtt"] += (ack_timestamp - pn_timestamp)
                        totals["rtt_amount"] += 1
                        acked_packets.append(index)
                for acked_packet in acked_packets:
                    del totals["unacked_packets"][acked_packet]
            except TypeError as t:
                print(t)
            except KeyError as e:
                print(e)
        return totals, run_avgs

    def getAckFrame(self, packet: dict):
        frames = packet['_source']['layers']["quic"]["quic.frame"]
        ackframe = None
        if isinstance(frames, list):
            for frame in frames:
                if frame["quic.frame_type"] == "2":
                    ackframe = frame
                    break
        else:
            if frames["quic.frame_type"] == "2":
                    ackframe = frames
        return ackframe
    
    def getAckRangesTCP(self, tcppacket: dict, ackranges: list):
        # parse SACK information
        if "tcp.options.sack_tree" in tcppacket['tcp.options_tree']:
            sack = tcppacket['tcp.options_tree']['tcp.options.sack_tree']
            left_egdes = sack['tcp.options.sack_le']
            right_edges = sack['tcp.options.sack_re']
            # check if there are multiple SACK ranges
            if isinstance(left_egdes, list):
                for index, gap in enumerate(left_egdes):
                    large_ack = int(right_edges[index])
                    low_ack = int(left_egdes[index])
                    ackranges.append({
                        "high_ack": large_ack,
                        "low_ack": low_ack
                    })
            else:
                large_ack = int(right_edges)
                low_ack = int(left_egdes)
                ackranges.append({
                    "high_ack": large_ack,
                    "low_ack": low_ack
                })

        return ackranges

    def getAckRangesQUIC(self, ackframe: dict, ackranges: list, large_ack: int):
        if "quic.ack.gap" in ackframe:
            ack_gaps = ackframe["quic.ack.gap"]
            range_lengths = ackframe["quic.ack.ack_range"]
            if isinstance(ack_gaps, list):
                for index, gap in enumerate(ack_gaps):
                    gap = int(gap) + 2
                    large_ack -= gap
                    range_length = int(range_lengths[index])
                    low_ack = large_ack - range_length
                    ackranges.append({
                        "high_ack": large_ack,
                        "low_ack": low_ack
                    })
                    large_ack = low_ack
            else:
                gap = int(ack_gaps) + 2
                large_ack -= gap
                range_length = int(range_lengths)
                low_ack = large_ack - range_length
                ackranges.append({
                    "high_ack": large_ack,
                    "low_ack": low_ack
                })

        return ackranges
    
    def isAcked(self, ackranges: list, pn: int, isquic: bool):
        acked = False
        if isquic:
            for ackrange in ackranges:
                if pn >= ackrange['low_ack'] and pn <= ackrange['high_ack']:
                    acked = True
                    break
        else:
            for ackrange in ackranges:
                if pn >= ackrange['low_ack'] and pn < ackrange['high_ack']:
                    acked = True
                    break
        return acked

    def addThroughputBytes(self, run_avgs: dict, bytes_amount: float, totals: dict, timestamp: float):
        run_avgs["avg_throughput"] += bytes_amount
        totals["tp_time"] = timestamp
        return totals, run_avgs
    
    def addGoodputBytes(self, run_avgs: dict, bytes_amount: float, totals: dict, timestamp: float):
        run_avgs["avg_goodput"] += bytes_amount
        totals["gp_time"] = timestamp
        return totals, run_avgs
    
    # for each test scenario: find median values from all runs
    def getMedianValues(self, runs: list):
        rtts = []
        cwnds = []
        goodputs = []
        throughputs = []
        medians = {}

        for run in runs:
            rtts.append(run["avg_rtt"])
            cwnds.append(run["avg_cwnd"])
            goodputs.append(run["avg_goodput"])
            throughputs.append(run["avg_throughput"])

        rtts.sort()
        cwnds.sort()
        goodputs.sort()
        throughputs.sort()

        middle = int(len(rtts) / 2)
        if len(rtts) == 1:
            middle = 0

        medians["mdn_rtt"] = rtts[middle]
        medians["mdn_cwnd"] = cwnds[middle]
        medians["mdn_goodput"] = goodputs[middle]
        medians["mdn_throughput"] = throughputs[middle]

        return medians

    def saveMetrics(self, outputdir: str):
        for id in range(0, len(self._metricsperfile)):
            medians = self.getMedianValues(self._metricsperfile[id]["runs"])
            self._metricsperfile[id]["mdn_goodput"] = medians["mdn_goodput"]
            self._metricsperfile[id]["mdn_throughput"] = medians["mdn_throughput"]
            self._metricsperfile[id]["mdn_rtt"] = medians["mdn_rtt"]
            self._metricsperfile[id]["mdn_cwnd"] = medians["mdn_cwnd"]
        with open(outputdir + "/metrics.json", mode='w') as metrics_file:
            json.dump(self._metricsperfile, metrics_file)
    
    def getMetrics(self):
        return self._metricsperfile