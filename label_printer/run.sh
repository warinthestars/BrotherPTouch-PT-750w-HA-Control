#!/bin/sh
# HA Supervisor mounts add-on options at /data/options.json
OPTIONS=/data/options.json

PRINTER_IP=$(jq -r '.printer_ip' "$OPTIONS")
PRINTER_PORT=$(jq -r '.printer_port' "$OPTIONS")
TAPE_WIDTH_MM=$(jq -r '.tape_width_mm' "$OPTIONS")
FONT_SIZE=$(jq -r '.font_size' "$OPTIONS")

export PRINTER_ADDR="tcp://${PRINTER_IP}:${PRINTER_PORT}"
export TAPE_WIDTH_MM
export FONT_SIZE
export LISTEN_ADDR=":8765"

echo "Starting label-printer on ${LISTEN_ADDR}"
echo "Printer: ${PRINTER_ADDR} | tape: ${TAPE_WIDTH_MM}mm | font: ${FONT_SIZE}pt"

exec /usr/local/bin/label-printer
