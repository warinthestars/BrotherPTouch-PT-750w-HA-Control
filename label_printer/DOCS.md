# Label Printer add-on

Drives a Brother PT-P750W label printer over WiFi (TCP port 9100) and exposes a plain HTTP API on port **8765**.

## Prerequisites

- A PT-P750W joined to your network with a **static IP** (set a DHCP reservation in your router)
- A TZe tape cassette loaded (6/9/12/18/24 mm)

## Options

| Option | Default | Description |
|---|---|---|
| `printer_ip` | `192.168.1.100` | Your printer's static IP address |
| `printer_port` | `9100` | Brother raster protocol port. Don't change unless you know why |
| `tape_width_mm` | `24` | Fallback tape width in mm (`6`, `9`, `12`, `18`, `24`). Only used when auto-detection is off or fails |
| `auto_tape_width` | `true` | Ask the printer what tape is loaded before each print. Recommended — prevents size-mismatch errors when you swap cassettes |
| `font_size` | `40` | **Maximum** font size in points. Text automatically shrinks to fit the tape, so this only caps how large short labels get |
| `date_format` | `Jan 2, 2006` | [Go time layout](https://pkg.go.dev/time#pkg-constants) for date lines. Examples: `Jan 2, 2006` → *Jul 1, 2026*, `2006-01-02` → *2026-07-01*, `01/02/06` → *07/01/26* |
| `time_format` | `3:04 PM` | Go time layout for time lines (`15:04` for 24-hour) |
| `log_level` | `info` | `info`: startup, print jobs, errors. `debug`: adds every HTTP request with source address, printer dial timing/results, status decode, and raw protocol tracing |

## HTTP API

### `POST /print`

Everything except `text` is optional; omitted fields use the options above.

```jsonc
{
  "text": "Breakfast Potatoes",                     // line 1 (required)
  "date": { "offset_days": 0, "offset_weeks": 0 },  // add a date line; offsets for expiry dates
  "time": true,                                     // append the current time to the date line
  "line2": "raw text",                              // explicit line 2 (overrides date/time)
  "copies": 3,                                      // 1–20, each copy cut separately
  "font_size": 40,                                  // max pt for this job
  "autocut": true,
  "mirror": false,
  "half_cut": false,
  "chain_print": false,
  "high_dpi": false,
  "feed_amount": 10
}
```

Response: `{"status":"printed","text":"...","line2":"...","copies":1,"tape_width_mm":24}`

### Other endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness check, returns `ok` |
| `/status` | GET | Live printer status: `online`, `model`, `battery`, `errors[]`, `media_type`, `tape_color`, `tape_width_mm`, `tape_length_mm`, `phase`, … When the printer is unreachable, returns HTTP 200 with `online: false` and a `detail` field |
| `/config` | GET | The add-on's effective configuration (answered from memory, never touches the printer) |
| `/feed` | POST | Feed and cut blank tape |
| `/test` | POST | Print a test label with the detected tape info and a timestamp |

## Behavior notes

- **All printer access is serialized** — status polls can never corrupt an in-flight print job.
- **Printer I/O is bounded** — 5 s connect timeout, 15 s status deadline, 90 s print deadline. A sleeping or unplugged printer makes requests fail fast instead of hanging.
- **Two-line layout** — line 1 gets ~62 % of the printable height, line 2 ~38 %, both auto-fit and centered. Printable height per tape: 24 mm → 128 px, 18 mm → 96 px, 12 mm → 64 px, 9 mm → 48 px, 6 mm → 32 px (180 dpi).
- **Security** — the API is unauthenticated on your LAN. Don't expose port 8765 to the internet.

## Troubleshooting

- **`/status` shows `online: false`** — the add-on is fine but can't reach the printer. Check the `detail` field, wake the printer (it sleeps), and verify `printer_ip`.
- Set `log_level: debug` and watch the add-on log to see every request and printer dial attempt in real time.
