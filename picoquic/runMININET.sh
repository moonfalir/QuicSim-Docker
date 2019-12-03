CURTIME=$(date +%Y-%m-%d-%H-%M) \
CLIENT="picoquic" \
CLIENT_PARAMS="-L -b /logs/clientpico_mn.log 10.0.0.251 4443 0:/5000000;" \
SERVER="picoquic" \
SERVER_PARAMS="-1 -L -b /logs/serverpico_mn.log" \
SCENARIO="simple_p2p --delay=15ms --bandwidth=5 --queue=25" \
LOGDIR="$PWD" \
CL_COMMIT="" \
SV_COMMIT="" \
docker-compose -f ../containernet/docker-compose.yml up