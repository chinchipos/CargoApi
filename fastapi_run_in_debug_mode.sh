#!/usr/bin/bash
source /home/cargo/env/bin/activate
cd /home/cargo/cargonomica/api
fastapi dev src/main.py --host 0.0.0.0 --port 8067
