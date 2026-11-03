#!/bin/sh
# Builds a Plaso storage file, then exports it as JSON lines. Usage: run_plaso.sh <evidence> <out>
# --single_process: Plaso's multi-process mode can stall inside containers; single process is
# slower on huge images but reliable.
set -eu
ev="$1"; out="$2"
log2timeline.py --single_process --unattended --status_view none \
  --storage_file "$out/timeline.plaso" "$ev"
psort.py --status_view none --output_time_zone UTC -o json_line \
  -w "$out/timeline.jsonl" "$out/timeline.plaso"
echo "events: $(wc -l < "$out/timeline.jsonl")"
