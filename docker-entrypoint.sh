#!/bin/sh
# Fix ownership of mounted folders (Linux bind mounts are created as root), then drop to the
# unprivileged 'tracelume' user for the actual process.
set -e
if [ "$(id -u)" = 0 ]; then
  for d in /data /data/evidence /data/workspace /backups; do
    [ -d "$d" ] && chown tracelume "$d" 2>/dev/null || true
  done
  exec setpriv --reuid=tracelume --regid=tracelume --init-groups "$@"
fi
exec "$@"
