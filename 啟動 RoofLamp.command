#!/bin/bash
cd "$(dirname "$0")"
(sleep 1; open "http://localhost:8090/index.html?v=$(date +%s)") &
python3 server.py 8090
