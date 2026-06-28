# PTouch Label Printer — Home Assistant Integration

Voice-triggered label printing for the **Brother PT-P750W** via Home Assistant. Say "Hey Google, talk to Home Assistant, print a label saying Spices" and a label prints. No app, no fiddling.

Built on top of [ptouchgo](https://github.com/ka2n/ptouchgo) (MIT), a Go driver for Brother P-touch printers over TCP.

---

## Architecture

Two components, both live in this repo:

```
label-printer-addon/      ← HA add-on: Go HTTP server that drives the printer
ha-integration/           ← HA custom integration: config flow UI + Assist voice wiring
```

The add-on is the print engine. It exposes a single `POST /print` endpoint inside your HA network. The integration is a thin Python layer that registers a `notify.label_printer` entity and handles Assist voice intents — no manual YAML editing required.

```
Google Assistant
      │  "Hey Google, talk to Home Assistant"
      ▼
HA Assist (conversation pipeline)
      │  matches custom sentence → PrintLabel intent
      ▼
label_printer integration (intent.py)
      │  POST /print {"text": "..."}
      ▼
label-printer add-on (Go HTTP server, port 8765)
      │  TCP raster protocol
      ▼
Brother PT-P750W (192.168.1.75:9100)
```

---

## Requirements

- Brother PT-P750W connected over **WiFi** with a static IP (USB is not supported)
- Home Assistant OS (HAOS) on a dedicated box, Pi, or VM
- HA add-on store access (Samba, Studio Code Server, or SSH to copy files)

---

## Installation

### Step 1 — Install the Add-on

The add-on is a Docker container that runs a Go HTTP server. It handles text rendering and communicates with the printer over TCP port 9100.

**Copy the add-on files to HAOS:**

Via Samba:
1. Connect to `\\<ha-ip>\addons` (Windows) or `smb://<ha-ip>/addons` (Mac)
2. Copy the `label-printer-addon/` folder into the share root → it lands at `/addons/local/label_printer/`

Via Studio Code Server (VS Code in browser):
1. Open Studio Code Server from the HA add-on panel
2. Navigate to `/addons/local/`, create a `label_printer/` folder
3. Upload all files from `label-printer-addon/`

Via SSH:
```bash
scp -r label-printer-addon/ root@<ha-ip>:/addons/local/label_printer/
```

**Install in HA:**
1. Settings → Add-ons → Add-on Store → ⋮ → **Check for updates**
2. Find **Label Printer** under Local add-ons → **Install**
   *(First build takes 2–3 minutes — Docker is compiling the Go binary)*
3. Go to the **Configuration** tab and set:
   - **Printer IP** — your PT-P750W's static IP
   - **Printer Port** — `9100` (Brother default, don't change)
   - **Tape Width (mm)** — width of tape currently loaded (`6`, `9`, `12`, `18`, or `24`)
   - **Font Size (pt)** — for 24 mm tape, `40` is a good default; scale up or down to taste
4. **Start** the add-on
5. Check the **Log** tab — you should see:
   ```
   label-printer starting: listen=:8765 printer=tcp://192.168.1.75:9100 tape=24mm font=40pt
   ```

### Step 2 — Install the Integration

The integration creates a `notify.label_printer` entity and wires up Assist voice commands.

**Copy the integration files to HAOS:**

Via Samba:
1. Connect to `\\<ha-ip>\config`
2. Navigate into `custom_components/` (create it if it doesn't exist)
3. Copy the `ha-integration/custom_components/label_printer/` folder in

Via SSH:
```bash
scp -r ha-integration/custom_components/label_printer/ \
    root@<ha-ip>:/config/custom_components/label_printer/
```

**Add the integration in HA:**
1. Restart Home Assistant
2. Settings → Devices & Services → **Add Integration**
3. Search for **Label Printer**
4. Enter the host (`localhost` if using the add-on, or the IP if running externally) and port (`8765`)
5. The config flow hits `/health` to confirm the add-on is reachable, then creates the integration

You should now have a **Label Printer** device with a `notify.label_printer` entity.

---

## Usage

### Voice (Google Assistant + Assist)

> "Hey Google, talk to Home Assistant"
> → "Print a label saying Spices"

Other phrases that work out of the box:
- "print a label that says Spices"
- "print Spices on a label"
- "make a label saying Spices"
- "label Spices"

Assist responds: *"Printing a label that says Spices."*

### HA Developer Tools

Services → `notify.send_message`:
```yaml
service: notify.send_message
target:
  entity_id: notify.label_printer
data:
  message: "Hello World"
```

### Automations & Scripts

```yaml
service: notify.send_message
target:
  entity_id: notify.label_printer
data:
  message: "{{ some_variable }}"
```

### Direct HTTP (testing / external tools)

```bash
curl -X POST http://<ha-ip>:8765/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```

Expected response:
```json
{"status": "printed", "text": "Hello World"}
```

Health check:
```bash
curl http://<ha-ip>:8765/health
```

---

## Configuration Reference

### Add-on options (`label-printer-addon/config.yaml`)

| Option | Default | Description |
|--------|---------|-------------|
| `printer_ip` | *(required)* | Static IP of your PT-P750W |
| `printer_port` | `9100` | TCP port — Brother standard, don't change |
| `tape_width_mm` | `24` | Tape width in mm. Valid: `6`, `9`, `12`, `18`, `24` |
| `font_size` | `40` | Font size in points at 180 dpi. For 24 mm tape, 40 pt fits well |

**Font sizing guide:** the PT-P750W prints at 180 dpi. The printable dot width per tape size is:

| Tape | Printable dots |
|------|---------------|
| 24 mm | 128 px |
| 18 mm | 96 px |
| 12 mm | 64 px |
| 9 mm | 48 px |
| 6 mm | 32 px |

At 180 dpi, font size in points × 2.5 ≈ em-square in pixels. Keep your font size comfortably below the printable dot height for your tape size.

### Integration options

Set during the config flow. Can be changed via Settings → Devices & Services → Label Printer → **Configure**.

| Option | Description |
|--------|-------------|
| `host` | Hostname or IP of the add-on (`localhost` for HAOS) |
| `port` | HTTP port of the add-on (default `8765`) |

---

## Troubleshooting

**Config flow shows "Invalid handler specified"**
The integration failed to import. Check HA logs (Settings → System → Logs, filter `label_printer`) for the actual Python error. Most common causes: files not fully copied, or a restart didn't pick up the new files.

**Add-on log shows `image size must have Npx width or height`**
The tape width configured in the add-on doesn't match what's loaded in the printer. Update the `tape_width_mm` option to match the actual tape.

**Print succeeds but text is clipped top/bottom**
Reduce `font_size`. At 24 mm (128 px), values above ~50 pt will start clipping.

**Printer unreachable**
- Confirm the printer's WiFi IP hasn't changed (set a DHCP reservation)
- The add-on and printer must be on the same network segment
- Test directly: `curl http://<ha-ip>:8765/health` (add-on up?) then `nc -zv <printer-ip> 9100` (printer reachable?)

**Assist doesn't understand the voice command**
- Restart HA after installing the integration (sentences are loaded at startup)
- Check that the integration is loaded: Settings → Devices & Services → Label Printer should show the device

---

## How It Works

The add-on is a Go HTTP server built directly against the `ptouchgo` library. When a print request arrives:

1. Text is rendered to a grayscale `image.Gray` using the Go Regular font at the configured DPI and font size
2. `ptouchgo.LoadRawImage()` packs it into the printer's raster format
3. `ptouchgo.CompressImage()` applies PackBits compression
4. The printer is opened over TCP (`tcp://<ip>:9100`), configured with the same command sequence as the upstream CLI (`Reset → SetRasterMode → SetPrintProperty → SetPrintMode → SetExtendedMode → SetFeedAmount → SetCompressionModeEnabled → SendImage → PrintAndEject`), and the job is sent

The integration's `intent.py` registers a `PrintLabel` intent handler at startup. The `sentences/en.yaml` file bundled with the integration teaches Assist the trigger phrases — no `custom_sentences/` directory or `intent_script:` block in `configuration.yaml` needed.

---

## License

MIT — see individual file headers. Built on [ptouchgo](https://github.com/ka2n/ptouchgo) by [@ka2n](https://github.com/ka2n), also MIT.
