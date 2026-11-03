#!/bin/sh
# run_mvt.sh <evidence> <out> <kind>: MVT check against bundled public IOCs.
set -eu
src="$(python /opt/stage.py "$1" "$2")"
case "$3" in
  ios_backup)
    dir="$(find "$src" -name Manifest.db -printf '%h\n' -quit)"
    mvt-ios check-backup --output "$2/mvt" "${dir:-$src}" ;;
  ios_fs) mvt-ios check-fs --output "$2/mvt" "$src" ;;
  *) echo "unsupported evidence kind $3" >&2; exit 2 ;;
esac
