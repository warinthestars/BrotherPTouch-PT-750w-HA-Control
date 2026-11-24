# Label Printer — Brother PT-P750W for Home Assistant

Voice-controlled label printing for the **Brother PT-P750W** over WiFi, fully integrated into Home Assistant.

> *"Print a label with today's date that says breakfast potatoes"*

…spoken into any HA Assist entry point prints a two-line label — text on top, date beneath, auto-sized to your tape — and cuts it. No Brother app, no computer, no YAML.

Built on [ptouchgo](https://github.com/ka2n/ptouchgo) (MIT), a Go driver for Brother P-touch printers.

## Features

- **Voice printing via HA Assist** — free-form label text captured from speech, with natural variations ("print a label saying…", "make a label that says…", "label spices")
- **Date & expiry labels** — "with today's date", "with the date and time", "expiring in 5 days", "good for in 2 weeks"
- **Multiple copies** — "print 3 labels saying spice jar", each cut separately
- **Two-line rendering with auto-fit** — text auto-sizes to the tape; dates render smaller under the main text
- **Automatic tape detection** — reads the loaded tape width from the printer before each print, so swapping 24 mm for 12 mm tape just works
- **Full device in HA** — printer status sensors (tape width/color, media type, battery, errors, connectivity), per-job print controls (font size, auto-cut, mirror, half-cut, chain printing, high-DPI, feed), and feed/test buttons
- **Plain HTTP API** — drive it from automations, scripts, `curl`, or anything else on your network
- **Zero YAML** — config flows and UI options everywhere; the Assist sentence file installs itself

## How it works

Two components, both in this repository:

```
label_printer/                      HA add-on — Go HTTP server that drives the printer
custom_components/label_printer/    HA custom integration — config flow, entities, voice wiring
```

```
Voice input (HA companion app mic · Assist dialog · Voice PE / ESPHome satellite)
      │
      ▼
HA Assist (conversation pipeline)
      │  matches sentence → PrintLabel intent (text, date, copies, … slots)
      ▼
label_printer integration
      │  POST /print {"text": "...", "date": {...}, "copies": N, ...}
      ▼
label-printer add-on (Go HTTP server, port 8765)
      │  Brother raster protocol over TCP (all printer access serialized)
      ▼
Brother PT-P750W (WiFi, port 9100)
```

The add-on renders text to a bitmap, converts it to the Brother raster format, and talks to the printer directly over TCP. The integration is a thin Python layer: it polls the add-on for printer status, exposes the entities, and maps Assist voice intents onto the HTTP API.

## Requirements

- **Brother PT-P750W** connected to your network over WiFi (USB is not supported)
- **Home Assistant OS or Supervised** (the print engine ships as an add-on)
- A way to copy files to your HA box: Samba, Studio Code Server, or SSH

> **Before you start:** give the printer a static IP. Find its current address in your router's client list (or print the network config by holding the feed button), then create a DHCP reservation for it. The examples below use `192.168.1.100` — substitute your printer's IP.

## Installation

### Part 1 — The add-on (print engine)

**1. Get the add-on into your store — two options:**

*Option A — add this repository (recommended):* Settings → Add-ons → Add-on Store → **⋮** → **Repositories** → add this repo's GitHub URL. **Label Printer** appears in the store under the new repository.

*Option B — copy the folder manually:* place `label_printer/` at `/addons/local/label_printer/` via the Samba `addons` share, SSH (`scp -r label_printer/ root@<ha-ip>:/addons/local/label_printer/`), or Studio Code Server. Then Add-on Store → **⋮** → **Check for updates**; it appears under *Local add-ons*.

**2. Install it.**
Click **Label Printer** → **Install**. The first build compiles the Go binary and takes 2–3 minutes.

**3. Configure it** (Configuration tab):

| Option | What to set |
|---|---|
| Printer IP | Your PT-P750W's static IP |
| Printer port | Leave at `9100` |
| Tape width | Width in mm of the loaded tape (`6`/`9`/`12`/`18`/`24`) — only used as a fallback when auto-detection is off or fails |
| Auto tape width | Leave **on** (recommended) |
| Font size | Maximum text size in pt; text auto-shrinks to fit. `40` is a good default |
| Date format / Time format | [Go time layouts](https://pkg.go.dev/time#pkg-constants): `Jan 2, 2006` → *Jul 1, 2026* · `2006-01-02` → *2026-07-01* · `01/02/06` → *07/01/26* |
| Log level | `info` normally; `debug` for troubleshooting |

**4. Start it** and check the Log tab for:
```
label-printer 1.1.2 starting: listen=:8765 printer=tcp://192.168.1.100:9100 tape=24mm font=40pt auto_tape=true log=info
```

**5. Smoke-test from any machine on your network:**
```bash
curl http://<ha-ip>:8765/health     # → ok
curl http://<ha-ip>:8765/status    # → {"online":true,"model":"PT-P750W",...}
```
If `online` is `false`, the add-on is fine but can't reach the printer — check the IP and that the printer is awake.

### Part 2 — The integration (entities + voice)

**1. Copy `custom_components/label_printer/` into your HA config directory** so it lands at `/config/custom_components/label_printer/` (via the Samba `config` share, SSH, or Studio Code Server).

**2. Restart Home Assistant** (required for HA to discover the new integration).

**3. Add it:** Settings → Devices & Services → **Add Integration** → search **Label Printer**.

**4. Connection settings:** keep the defaults — host `localhost`, port `8765`. The add-on publishes its port on the host, so `localhost` works no matter how the add-on was installed, and keeps working if you reinstall it from a different source. (The add-on's internal hostname — shown on its info page, e.g. `local-label-printer` or `<repo-hash>-label-printer` for repository installs — also works, as does an IP if the print server runs on another machine.) The host and port can be changed later via the integration's ⋮ → **Reconfigure**.

The integration verifies the add-on is reachable and creates the device. The printer itself does **not** need to be on for setup — its state shows up on the Online sensor.

On first setup the integration also installs its Assist sentence file to `/config/custom_sentences/en/label_printer.yaml` and reloads the conversation agent, so voice commands work immediately. (HA doesn't load sentence files bundled inside integrations — this copy step is how the zero-YAML promise is kept. The installed file is only overwritten on updates while its first line still reads `# managed by label_printer`; remove that line if you customize it.)

### Part 3 — First label

1. Load a tape cassette and power on the printer
2. Press the **Test print** button on the Label Printer device page — it prints the detected tape info and a timestamp
3. Open Assist (mic icon in the companion app, or the Assist dialog in the web UI) and say: *"print a label saying hello world"*

## Voice usage

Speak into any Assist entry point: the HA companion app mic, the Assist dialog, or a voice satellite (Home Assistant Voice PE, ESPHome voice satellite, Wyoming). If you use a Google/Alexa speaker, note that Google Assistant's old "talk to Home Assistant" conversational bridge no longer exists — an Assist-native input is required for free-form label text.

| Say | Prints |
|---|---|
| "print a label saying spices" | `Spices` |
| "print a label with today's date saying breakfast potatoes" | `Breakfast Potatoes` over `Jul 1, 2026` |
| "print a label saying leftovers with the date and time" | `Leftovers` over `Jul 1, 2026 6:42 PM` |
| "print a label saying yogurt expiring in 5 days" | `Yogurt` over `Jul 6, 2026` |
| "print a label saying stew good for in 2 weeks" | `Stew` over `Jul 15, 2026` |
| "print 3 labels saying spice jar" | three cut copies |
| "print 2 labels with the date" | two cut labels showing just today's date |

Accepted variations: "make a label…", "label spices", "that says / saying / with the text / for", "dated", "expires N days from now", "good for N weeks", filler like "can you… please", number words ("two labels"), and common mishearings ("print a level…", "print to labels…"). A date phrase the text wildcard swallows ("…saying soup with the date") is still applied as the date rather than printed. Phrasings with the modifier *before* the text ("…with today's date saying X") parse most reliably.

## Entities

| Entity | Type | Purpose |
|---|---|---|
| `notify.label_printer` | notify | Prints `message` as a label; optional `title` becomes the smaller second line |
| Online | binary sensor | Printer reachable over TCP (the exact error is an attribute when off) |
| Problem | binary sensor | Any printer error active (cover open, no media, cutter jam, …) |
| Tape width | sensor | Width (mm) of the tape actually loaded |
| Tape color / Text color | sensor | Loaded cassette colors |
| Media type / Battery / Model / Error / Phase / Status | sensor (diagnostic) | Printer diagnostics |
| Font size | number | Maximum font size in pt; `0` = use the add-on default |
| Feed amount | number | Feed dots before cut |
| Auto cut / Mirror / Half cut / Chain printing / High DPI | switch | Per-job print flags applied to every print |
| Feed and cut | button | Feeds and cuts blank tape |
| Test print | button | Prints detected tape info + timestamp |

Status polls every 60 s by default (Settings → Devices & Services → Label Printer → **Configure**). Polling is safe during prints — the add-on serializes all printer access.

## Automations & scripts

```yaml
# Print a label from any automation
action: notify.send_message
target:
  entity_id: notify.label_printer
data:
  message: "Leftover Chili"
  title: "{{ now().strftime('%b %-d, %Y') }}"   # optional second line
```

## HTTP API

The add-on exposes a plain HTTP API on port 8765 — usable from anything on your network.

```bash
curl -X POST http://<ha-ip>:8765/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Breakfast Potatoes", "date": {}, "copies": 2}'
```

`POST /print` — everything except `text` is optional:

```jsonc
{
  "text": "Breakfast Potatoes",                     // line 1 (required)
  "date": { "offset_days": 0, "offset_weeks": 0 },  // add a date line; offsets for expiry dates
  "time": true,                                     // append the current time to the date line
  "line2": "raw text",                              // explicit line 2 (overrides date/time)
  "copies": 3,                                      // 1–20, each copy cut separately
  "font_size": 40,                                  // max pt; auto-fit shrinks to fit the tape
  "autocut": true,
  "mirror": false,
  "half_cut": false,
  "chain_print": false,
  "high_dpi": false,
  "feed_amount": 10
}
```

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness (`ok`) |
| `/status` | GET | Live printer status: `online`, `model`, `battery`, `errors[]`, `media_type`, `tape_color`, `tape_width_mm`, `phase`, … Returns `online: false` + `detail` when the printer is unreachable |
| `/config` | GET | Effective add-on configuration (never touches the printer) |
| `/feed` | POST | Feed and cut |
| `/test` | POST | Print a test label with detected tape info |

> The API is unauthenticated and bound to your LAN — anyone on your network can print labels. Don't port-forward it.

## Configuration reference

### Add-on options

| Option | Default | Description |
|--------|---------|-------------|
| `printer_ip` | `192.168.1.100` | Static IP of your PT-P750W |
| `printer_port` | `9100` | Brother raster port — don't change |
| `tape_width_mm` | `24` | Fallback tape width (mm): `6`, `9`, `12`, `18`, `24` |
| `auto_tape_width` | `true` | Detect the loaded tape from the printer before each print |
| `font_size` | `40` | **Maximum** font size in pt; text auto-shrinks to fit |
| `date_format` | `Jan 2, 2006` | Go time layout for date lines |
| `time_format` | `3:04 PM` | Go time layout for time lines |
| `log_level` | `info` | `info` = startup, prints, errors. `debug` = + every HTTP request with source address, printer dial/status detail, raw protocol tracing |

**Rendering notes:** the PT-P750W prints at 180 dpi. Printable dot height per tape: 24 mm → 128 px, 18 mm → 96 px, 12 mm → 64 px, 9 mm → 48 px, 6 mm → 32 px. On two-line labels, line 1 gets ~62 % of the height, line 2 ~38 %.

### Integration options

Settings → Devices & Services → Label Printer → **Configure**: status poll interval (10–3600 s). Print settings (font size, auto-cut, mirror, …) live on the device as number/switch entities and are sent with every print.

## Troubleshooting

**Integration loads but printer entities show unavailable / Online is off**
By design the integration only requires the *add-on* to be reachable; printer state is the Online sensor's job. Check the sensor's `detail` attribute for the exact TCP error. The PT-P750W sleeps — press any button on it, and verify its IP hasn't changed (use a DHCP reservation). Set the add-on's `log_level: debug` to watch each status poll and dial result live.

**Config flow can't reach the add-on**
Confirm the add-on is running and `curl http://<ha-ip>:8765/health` answers from another machine. Use host `local-label-printer` in the flow. The exact failure (DNS, refused, timeout) is logged under Settings → System → Logs — search `label_printer`.

**"Invalid handler specified" when adding the integration**
The integration failed to import — usually an incomplete copy. Re-copy the whole `custom_components/label_printer/` folder, restart HA, and check the logs for the underlying Python error.

**Assist doesn't understand the commands**
Verify `/config/custom_sentences/en/label_printer.yaml` exists (the integration installs it at setup), then Developer Tools → Actions → `conversation.reload`, or restart HA. Prefer modifier-first phrasing: "print a label with today's date saying X".

**Add-on log shows `image size must have Npx width or height`**
Tape-size mismatch between renderer and printer. With `auto_tape_width: true` (default) this shouldn't occur — check the Tape width sensor to see what the printer reports.

**Text is clipped top/bottom**
Shouldn't happen with auto-fit; if it does, lower the Font size entity (or set `0` for full auto).

## Updating

**Add-on** (repository install): updates are push-driven. When a new version is published (the `version:` in `label_printer/config.yaml` changes), the Add-on Store shows an **Update** button — force a check via Add-on Store → ⋮ → **Check for updates**. The update rebuilds the add-on in place; your options are preserved. Local-copy installs: re-copy the folder, then Check for updates.

**Integration**: Home Assistant does not pull custom integrations from git. Either install it via [HACS](https://hacs.xyz) (HACS → Custom repositories → this repo's URL, type *Integration*) to get one-click updates when a new version is tagged, or re-copy `custom_components/label_printer/` and restart HA. Config entries, entity settings, and your customized sentence file survive updates.

## Development

The add-on is a single-file Go HTTP server (`label_printer/main.go`) built directly against the ptouchgo library — the Dockerfile compiles it during add-on installation, no toolchain needed on your machine. The integration is standard HA custom-component Python; sentence patterns live in `custom_components/label_printer/sentences/en.yaml` and can be validated offline with [hassil](https://github.com/OHF-Voice/hassil).

Print pipeline: render text → `image.Gray` (auto-fit per line) → `ptouchgo.LoadRawImage` → PackBits compression → TCP session (`Reset → SetRasterMode → SetPrintProperty → SetPrintMode → SetExtendedMode → SetFeedAmount → SetCompressionModeEnabled [→ SetAutocutPerPagesForPTP750W]`) → `SendImage` + `Print`/`PrintAndEject` per copy. All printer I/O is mutex-serialized with bounded dial timeouts and connection deadlines.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). See [CHANGELOG.md](CHANGELOG.md) for release history. Add-on and integration versions may advance independently; the changelog labels each change.

## Compatibility

- **Printer:** Brother PT-P750W (network/WiFi). Other P-touch models supported by ptouchgo (PT-710BT, PT-700) may work over TCP but are untested.
- **Tape:** TZe cassettes, 6/9/12/18/24 mm.
- **Home Assistant:** HAOS or Supervised (the print engine is an add-on). Tested on 2026.x.

## License & credits

MIT — see [LICENSE](LICENSE).

Built on [ptouchgo](https://github.com/ka2n/ptouchgo) by [@ka2n](https://github.com/ka2n) (MIT). Not affiliated with or endorsed by Brother Industries.
