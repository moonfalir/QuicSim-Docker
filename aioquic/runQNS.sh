CURTIME=$(date +%Y-%m-%d-%H-%M) \
CLIENT="aioquic" \
CLIENT_PARAMS="--ca-certs tests/pycacert.pem -q /logs/clientaioquic_$CURTIME.qlog --legacy-http https://193.167.100.100:4433/5000000" \
SERVER="aioquic" \
SERVER_PARAMS="--certificate tests/ssl_cert.pem --private-key tests/ssl_key.pem --host 193.167.100.100 -q /logs" \
SCENARIO="simple-p2p --delay=15ms --bandwidth=10Mbps --queue=25" \
LOGDIR="$PWD/logs" \
docker-compose -f ../quic-network-simulator/docker-compose.yml up --abort-on-container-exit