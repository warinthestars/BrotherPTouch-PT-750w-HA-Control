# Label Printer add-on

Print labels on a **Brother PT-P750W** over WiFi via a simple HTTP API.

This add-on is the print engine behind the Label Printer custom integration: it renders text (one or two lines, auto-fit to your tape), converts it to the Brother raster format, and sends it to the printer over TCP port 9100.

Features: two-line labels with date/time/expiry support, multiple cut copies, automatic tape-width detection, live printer status (`/status`), feed & test endpoints, and configurable date/time formats.

Pair it with the `label_printer` custom integration from the same repository for Home Assistant entities and Assist voice control ("print a label with today's date that says breakfast potatoes"), or drive it directly:

```bash
curl -X POST http://<ha-ip>:8765/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World", "date": {}}'
```

See the **Documentation** tab for options and the full API.
