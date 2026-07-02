#!/bin/sh
# HA Supervisor mounts add-on options at /data/options.json
OPTIONS=/data/options.json

PRINTER_IP=$(jq -r '.printer_ip' "$OPTIONS")
PRINTER_PORT=$(jq -r '.printer_port' "$OPTIONS")
TAPE_WIDTH_MM=$(jq -r '.tape_width_mm' "$OPTIONS")
FONT_SIZE=$(jq -r '.font_size' "$OPTIONS")
DATE_FORMAT=$(jq -r '.date_format // "Jan 2, 2006"' "$OPTIONS")
TIME_FORMAT=$(jq -r '.time_format // "3:04 PM"' "$OPTIONS")
# NB: jq's // operator replaces false as well as null, so `.x // true`
# would make it impossible to turn this off. Explicit null check instead.
AUTO_TAPE_WIDTH=$(jq -r 'if .auto_tape_width == null then true else .auto_tape_width end' "$OPTIONS")
LOG_LEVEL=$(jq -r '.log_level // "info"' "$OPTIONS")

export PRINTER_ADDR="tcp://${PRINTER_IP}:${PRINTER_PORT}"
export TAPE_WIDTH_MM
export FONT_SIZE
export DATE_FORMAT
export TIME_FORMAT
export AUTO_TAPE_WIDTH
export LOG_LEVEL
export LISTEN_ADDR=":8765"

echo "Starting label-printer on ${LISTEN_ADDR}"
echo "Printer: ${PRINTER_ADDR} | tape: ${TAPE_WIDTH_MM}mm (auto: ${AUTO_TAPE_WIDTH}) | font: ${FONT_SIZE}pt"
echo "Date format: ${DATE_FORMAT} | time format: ${TIME_FORMAT} | log: ${LOG_LEVEL}"

exec /usr/local/bin/label-printer
