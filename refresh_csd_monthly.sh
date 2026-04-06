#!/bin/bash

cd /Users/Shared/LMCP-AutoQuote-Server || exit 1

set -a
source .env
set +a

/usr/bin/python3 -m app.scripts.run_csd_report_refresh >> csd_refresh.log 2>&1
