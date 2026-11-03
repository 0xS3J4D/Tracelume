#!/bin/sh
# Builds a Plaso storage file, then exports it as JSON lines. Usage: run_plaso.sh <evidence> <out>
set -eu
ev="$1"; out="$2"
log2timeline.py --status_view linear --unattended --quiet \
  --storage_file "$out/timeline.plaso" "$ev"
psort.py --status_view none --output_time_zone UTC -o json_line \
  -w "$out/timeline.jsonl" "$out/timeline.plaso"
echo "events: $(wc -l < "$out/timeline.jsonl")"
