CURTIME=$(date +%Y-%m-%d-%H-%M) \
CLIENT="tcpebpf" \
CLIENT_PARAMS="iperf -n 5000000 -c 10.0.0.251 5001" \
SERVER="tcpebpf" \
SERVER_PARAMS="iperf -s" \
SCENARIO="blackhole --delay 15ms --bandwidth 5 --queue 25 --on 2 --off 3" \
LOGDIR="$PWD" \
docker-compose -f ../containernet/docker-compose.yml up