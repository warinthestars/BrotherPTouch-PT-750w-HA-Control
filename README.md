# PTouch Label Printer — Home Assistant Integration

Voice-triggered label printing for the **Brother PT-P750W** via Home Assistant. Say "print a label with today's date that says breakfast potatoes" into HA Assist — the companion app's mic, an Assist dialog, or a Voice PE satellite — and a two-line label prints. No app, no fiddling.

Built on top of [ptouchgo](https://github.com/ka2n/ptouchgo) (MIT), a Go driver for Brother P-touch printers over TCP.

---

## Architecture

Two components, both live in this repo:

```
label_printer/                      ← HA add-on: Go HTTP server that drives the printer
custom_components/label_printer/    ← HA custom integration: config flow, entities, Assist voice wiring
```

The add-on is the print engine — an HTTP API inside your HA network. The integration is a Python layer that registers a device with print/status/control entities and handles Assist voice intents — no manual YAML editing required.

```
Voice input (HA companion app mic · Assist dialog · Voice PE / ESPHome satellite)
      │
      ▼
HA Assist (conversation pipeline)
      │  matches custom sentence → PrintLabel intent (text, date, copies, … slots)
      ▼
label_printer integration
      │  POST /print {"text": "...", "date": {...}, "copies": N, ...}
      ▼
label-printer add-on (Go HTTP server, port 8765)
      │  TCP raster protocol (serialized; status polls never collide with prints)
      ▼
Brother PT-P750W (WiFi, port 9100)
```

---

## Requirements

- Brother PT-P750W connected over **WiFi** with a static IP (USB is not supported)
- Home Assistant OS (HAOS) on a dedicated box, Pi, or VM
- Samba, Studio Code Server, or SSH access to copy files

---

## Installation

### Step 1 — Install the Add-on

**Copy the add-on files to HAOS:**

Via Samba:
1. Connect to `\\<ha-ip>\addons` (Windows) or `smb://<ha-ip>/addons` (Mac)
2. Copy the `label_printer/` folder into the share root → it lands at `/addons/local/label_printer/`

Via Studio Code Server (VS Code in browser):
1. Open Studio Code Server from the HA add-on panel
2. Navigate to `/addons/local/`, create a `label_printer/` folder
3. Upload all files from `label_printer/`

Via SSH:
```bash
scp -r label_printer/ root@<ha-ip>:/addons/local/label_printer/
```

**Install in HA:**
1. Settings → Add-ons → Add-on Store → ⋮ → **Check for updates**
2. Find **Label Printer** under Local add-ons → **Install**
   *(First build takes 2–3 minutes — Docker is compiling the Go binary)*
3. Go to the **Configuration** tab (see [Add-on options](#add-on-options-label_printerconfigyaml))
4. **Start** the add-on
5. Check the **Log** tab — you should see:
   ```
   label-printer 1.1.0 starting: listen=:8765 printer=tcp://192.168.1.75:9100 tape=24mm font=40pt auto_tape=true
   ```

### Step 2 — Install the Integration

**Copy the integration files to HAOS:**

Via Samba:
1. Connect to `\\<ha-ip>\config`
2. Navigate into `custom_components/` (create it if it doesn't exist)
3. Copy the `custom_components/label_printer/` folder in

Via SSH:
```bash
scp -r custom_components/label_printer/ \
    root@<ha-ip>:/config/custom_components/label_printer/
```

**Add the integration in HA:**
1. Restart Home Assistant
2. Settings → Devices & Services → **Add Integration**
3. Search for **Label Printer**
4. Enter the host and port (`8765`). Use **`local-label-printer`** (the add-on's internal hostname) — *not* `localhost`: HAOS publishes add-on ports on the LAN interface but doesn't proxy them over loopback, so `localhost` fails from inside HA core even when `<ha-ip>:8765` works from another machine. Only use an IP/hostname here if you run the print server somewhere else entirely.
5. The config flow hits `/health` to confirm the add-on is reachable, then creates the integration

On first setup the integration also installs its Assist sentence file to
`/config/custom_sentences/en/label_printer.yaml` and reloads the conversation
agent — voice commands work immediately, no restart needed. (HA does not load
sentence files bundled inside integrations, so this copy step is how the
"zero YAML" promise is kept. The file is only overwritten on updates while its
first line still reads `# managed by label_printer` — delete that line if you
customize it and want your edits preserved.)

You now have a **Label Printer** device with the full entity set below.

---

## Entities

| Entity | Type | What it does |
|---|---|---|
| `notify.label_printer` | notify | Prints `message` as a label (`title`, if given, becomes line 2) |
| Online | binary_sensor | Printer reachable over TCP (add-on reachable but printer down shows as off, with the error detail as an attribute) |
| Problem | binary_sensor | Any printer error bit set (cover open, no media, cutter jam, …) |
| Tape width | sensor | Width (mm) of the tape actually loaded, read from the printer |
| Tape color / Text color | sensor | Loaded cartridge colors |
| Media type / Battery / Model / Error / Phase / Status | sensor (diagnostic) | Raw printer diagnostics |
| Font size | number | Max font size in pt; `0` = use the add-on default (auto-fit) |
| Feed amount | number | Feed dots before cut |
| Auto cut / Mirror / Half cut / Chain printing / High DPI | switch | Per-job print flags, applied to every print |
| Feed and cut | button | Feeds and cuts blank tape |
| Test print | button | Prints detected tape info + timestamp |

Printer status is polled every 60 s by default (change under Settings → Devices & Services → Label Printer → **Configure**). Polling is safe during prints — the add-on serializes all printer access.

---

## Usage

### Voice (HA Assist)

Speak into any Assist entry point — the mic icon in the HA companion app, the Assist dialog in the web UI, or a voice satellite (Home Assistant Voice PE, ESPHome satellite, Wyoming). Google Assistant's old "talk to Home Assistant" conversational bridge no longer exists, so Assist is the voice path.

| Say | Prints |
|---|---|
| "print a label saying spices" | `Spices` |
| "print a label with today's date saying breakfast potatoes" | `Breakfast Potatoes` over `Jul 1, 2026` |
| "print a label saying leftovers with the date and time" | `Leftovers` over `Jul 1, 2026 6:42 PM` |
| "print a label saying yogurt expiring in 5 days" | `Yogurt` over `Jul 6, 2026` |
| "print a label saying stew good for in 2 weeks" | `Stew` over `Jul 15, 2026` |
| "print 3 labels saying spice jar" | three cut copies |

Variants like "make a label…", "label spices", "that says / saying / with the text" all work. Date-phrase-first wordings ("…with today's date saying X") are the most reliably parsed.

### HA Developer Tools

```yaml
service: notify.send_message
target:
  entity_id: notify.label_printer
data:
  message: "Hello World"
  title: "Jul 1, 2026"   # optional — becomes the smaller second line
```

### Direct HTTP (testing / automations / external tools)

```bash
curl -X POST http://<ha-ip>:8765/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Breakfast Potatoes", "date": {}, "copies": 2}'
```

Full request schema (everything except `text` is optional):

```jsonc
{
  "text": "Breakfast Potatoes",   // line 1 (required)
  "date": { "offset_days": 0, "offset_weeks": 0 },  // add date line; offsets for expiry dates
  "time": true,                    // append current time to the date line
  "line2": "raw text",             // explicit line 2 (overrides date/time)
  "copies": 3,                     // 1–20, each copy cut separately
  "font_size": 40,                 // max pt; auto-fit shrinks to fit tape
  "autocut": true,
  "mirror": false,
  "half_cut": false,
  "chain_print": false,
  "high_dpi": false,
  "feed_amount": 10
}
```

Other endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Add-on liveness (`ok`) |
| `/status` | GET | Live printer status JSON: `online`, `model`, `battery`, `errors[]`, `media_type`, `tape_color`, `tape_width_mm`, `phase`, … |
| `/config` | GET | Effective add-on configuration |
| `/feed` | POST | Feed and cut |
| `/test` | POST | Print a test label with detected tape info |

---

## Configuration Reference

### Add-on options (`label_printer/config.yaml`)

| Option | Default | Description |
|--------|---------|-------------|
| `printer_ip` | *(required)* | Static IP of your PT-P750W |
| `printer_port` | `9100` | TCP port — Brother standard, don't change |
| `tape_width_mm` | `24` | Fallback tape width in mm. Valid: `6`, `9`, `12`, `18`, `24` |
| `auto_tape_width` | `true` | Detect the loaded tape width from the printer before each print (recommended — eliminates size-mismatch errors when you swap tape) |
| `font_size` | `40` | *Maximum* font size in points; text auto-shrinks to fit the tape |
| `date_format` | `Jan 2, 2006` | [Go time layout](https://pkg.go.dev/time#pkg-constants) for date lines. `2006-01-02` → ISO, `01/02/06` → US short |
| `time_format` | `3:04 PM` | Go time layout for time lines |
| `log_level` | `info` | `info` = startup, prints, errors. `debug` = + every HTTP request with source address, printer dial/status detail, raw ptouchgo protocol tracing |

**Font sizing:** the PT-P750W prints at 180 dpi. Printable dot height per tape: 24 mm → 128 px, 18 mm → 96 px, 12 mm → 64 px, 9 mm → 48 px, 6 mm → 32 px. Fonts auto-fit, so `font_size` only caps how large a short label can get. On two-line labels, line 1 gets ~62% of the height and line 2 ~38%.

### Integration options

Settings → Devices & Services → Label Printer → **Configure**: host, port, status poll interval. Print settings (font size, autocut, mirror, …) are the number/switch entities on the device.

---

## Troubleshooting

**Config flow says the add-on can't be reached, but the container is running**
You probably entered `localhost` as the host. Use `local-label-printer` (see Step 2). Verify the add-on itself is fine from another machine: `curl http://<ha-ip>:8765/health`.

**Config flow shows "Invalid handler specified"**
The integration failed to import. Check HA logs (Settings → System → Logs, filter `label_printer`) for the actual Python error. Most common causes: files not fully copied, or a restart didn't pick up the new files.

**Add-on log shows `image size must have Npx width or height`**
The tape width used for rendering doesn't match what's loaded. With `auto_tape_width: true` (default) this shouldn't happen — if it does, check the Tape width sensor to see what the printer actually reports.

**Print succeeds but text is clipped top/bottom**
Shouldn't happen with auto-fit; if it does, lower the Font size number entity (or set it to 0 for full auto).

**Integration loads but printer entities show unavailable/off**
This is by design: the integration only requires the *add-on* to be reachable. Printer state is reported by the Online sensor. Set the add-on's `log_level: debug` and watch its log to see each status poll and the exact printer dial result.

**Printer unreachable / Online sensor off**
- Check the Online sensor's `detail` attribute for the exact TCP error
- Confirm the printer's WiFi IP hasn't changed (set a DHCP reservation)
- Test directly: `curl http://<ha-ip>:8765/status`

**Assist doesn't understand the voice command**
- Check `/config/custom_sentences/en/label_printer.yaml` exists (the integration installs it at setup)
- Reload: Developer Tools → Actions → `conversation.reload`, or restart HA
- Date/expiry phrasing works best with the modifier *before* the text: "print a label with today's date saying X"

---

## How It Works

The add-on is a Go HTTP server built directly against the `ptouchgo` library. When a print request arrives:

1. If `auto_tape_width` is on, the loaded tape width is read from the printer (`RequestStatus`/`ReadStatus`)
2. The date/time line is composed using the configured Go time layouts
3. Text is rendered to a grayscale `image.Gray` using the bundled Go Regular font at 180 dpi, auto-fit per line (62/38 split for two lines)
4. `ptouchgo.LoadRawImage()` packs it into the printer's raster format, `CompressImage()` applies PackBits
5. The printer is opened over TCP and configured (`Reset → SetRa