#!/bin/sh
# run.sh <evidence> <out>: Sigma/Hayabusa detections over all .evtx files, UTC, JSONL.
set -eu
src="$(python /opt/stage.py "$1" "$2")"
if [ -f "$src" ]; then input="-f $src"; else input="-d $src"; fi
# shellcheck disable=SC2086
/opt/hayabusa/hayabusa json-timeline $input -L -o "$2/hayabusa.jsonl" -w -U -O -N -K -C
