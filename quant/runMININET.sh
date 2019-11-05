CURTIME=$(date +%Y-%m-%d-%H-%M) \
CLIENT="quant" \
CLIENT_PARAMS="./bin/client -i client-eth0 -q /logs/clientmnquant_$CURTIME.qlog http://10.0.0.251:4433/50000" \
SERVER="quant" \
SERVER_PARAMS="./bin/server -d ./ -i server-eth0 -q /logs/servermnquant_$CURTIME.qlog" \
SCENARIO="droplist --delay 50ms --bandwidth 1 --queue 25 --drops_to_server=1,3,4 --drops_to_client=5" \
LOGDIR="$PWD" \
docker-compose -f ../containernet/docker-compose.yml up