#!/bin/sh
set -eu
umask 077

if [ "$#" -eq 0 ]; then
    set -- python /app/scripts/khoi_tao_production_noi_bo.py
fi

"$@"
unset AUTH_OWNER_PASSWORD_FILE
chown -R 10001:10001 /data /profile-volume-staging /models
find /profile-volume-staging -type d -exec chmod 0700 {} +
