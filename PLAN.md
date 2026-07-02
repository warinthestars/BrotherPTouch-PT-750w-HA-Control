# Plan: Label Variables + Full Printer Control/Diagnostics Surface

Decisions locked in (2026-07-01): two-line layout (text large, date smaller beneath),
date format "Jul 1, 2026" (Go layout `Jan 2, 2006`), variables = date + time + expiry
offsets + copies, full sensor/control surface in HA.

---

## Phase 1 — Go add-on (`label_printer/`)

### 1.1 Printer access serialization
Add a global `sync.Mutex` around every printer connection. ptouchgo's docs warn
`RequestStatus` must not run during a print; once `/status` polling exists, a poll
landing mid-print would corrupt the job. One mutex, held for the full
open→configure→print→close sequence, fixes this.

### 1.2 Multi-line rendering
Replace `renderLabel(text)` with `renderLabel(lines []renderLine)` where each line has
its own font size. For text+date: text gets ~62% of printable height, date ~38%,
sizes auto-fit to the allotted band (current `font_size` option becomes a *max*, not
fixed). Single-line labels keep today's behavior. Label width = widest line + padding.

### 1.3 Expanded `POST /print` body
All fields optional except `text`; omitted fields fall back to add-on config defaults:

```json
{
  "text": "Breakfast Potatoes",
  "date": { "offset_days": 0 },      // include date line; offset_days/offset_weeks for expiry
  "time": true,                       // append current time to the date line
  "line2": "raw override",            // explicit second line (wins over date/time)
  "copies": 3,
  "font_size": 40,
  "autocut": true, "mirror": false, "half_cut": false,
  "chain_print": false, "high_dpi": false, "feed_amount": 10
}
```

Date/time formatting lives **in the Go server** (configured via add-on options,
see 1.5) so the HA integration stays thin and format config has one home.
Copies: send raster once, `Print()` × (n−1), then `PrintAndEject()`, with
`SetAutocutPerPagesForPTP750W(1)` so each copy is cut.

### 1.4 New endpoints
- `GET /status` — acquire mutex, open printer, `RequestStatus()` + `ReadStatus()`,
  return JSON of every `Status` field (verified against pkg.go.dev v1.0.0):
  `model, battery, error1, error2, status_type, phase_type, phase, notification,
  media_type, tape_color, tape_length, tape_width_mm, font_color`, plus
  `online: true/false` (false + HTTP 200 when the TCP connect fails, so HA can
  distinguish "add-on up, printer down").
- `POST /feed` — feed configured amount and cut (blank mini-print).
- `POST /test` — print a test label: detected tape width + color + timestamp.

### 1.5 New add-on options (`config.yaml`, bump to 1.1.0)
- `date_format` (str, default `"Jan 2, 2006"`) — Go time layout
- `time_format` (str, default `"3:04 PM"`)
- `auto_tape_width` (bool, default `true`) — on each print, use tape width reported
  by the printer instead of the configured value. Eliminates the
  "image size must have Npx" failure mode when tape is swapped.

---

## Phase 2 — Assist sentences + intent handler

### 2.1 `sentences/en.yaml`
Add sentence groups that set fixed slot values (hassil `slots:` per data block):

- date: `"print a label with (today's date|the date) (that says|saying) {text}"` →
  `with_date: true` — plus the reversed order variant
- time: `"... with the (date and time|time)"` → `with_time: true`
- expiry: `"print a label (that says|saying) {text} (expiring|that expires|good for) in {count} (days|weeks)"`
  → `offset` + `unit` slots (`{count}` as a hassil number range 1–90)
- copies: `"print {copies} labels (that say|saying) {text}"` (range 2–20)

**Known risk to test:** hassil wildcards (`{text}`) are greedy — in trailing-modifier
patterns ("...saying {text} with today's date") the modifier can get swallowed into
`text`. Mitigation: prefer modifier-*before*-text patterns as primary, keep trailing
variants as best-effort, and validate all patterns offline with the `hassil` Python
package before deploying.

### 2.2 `intent.py`
Extend `slot_schema` with optional `with_date`, `with_time`, `offset`, `unit`,
`copies`. Map slots → the new `/print` JSON body. Speech response reflects what was
printed ("Printing 3 labels saying Breakfast Potatoes with today's date").

---

## Phase 3 — Integration entities (`custom_components/label_printer/`)

### 3.1 Coordinator
`DataUpdateCoordinator` polling `GET /status` (default every 60 s, configurable via a
new options flow). Printer wakes/connects per poll — cheap over TCP, and the add-on
mutex makes it safe.

### 3.2 New platforms
| Platform | Entities |
|---|---|
| `sensor` | tape width (mm), tape color, media type, tape length, battery, model, error text (Error1+Error2 decoded), phase/status — most flagged `entity_category: diagnostic` |
| `binary_sensor` | printer online (device class `connectivity`), problem (device class `problem`, any error bit set) |
| `number` | font size (pt, max), feed amount |
| `switch` | autocut, mirror, half-cut, high-DPI, chain print |
| `button` | feed & cut, test print |

Control-entity state is stored in config-entry options (survives restart) and merged
into every `/print` call from both the notify entity and the intent handler. All
entities hang off the existing PT-P750W device.

### 3.3 Housekeeping in the integration
`manifest.json` version bump; `strings.json`/`translations` for the options flow and
new entities.

---

## Phase 4 — Docs & repo hygiene

- **Fix README path drift:** README says `label-printer-addon/` and
  `ha-integration/custom_components/`; the real dirs are `label_printer/` and
  `custom_components/`. Update install instructions to match.
- Document new voice phrases, `/print` fields, `/status` API, and the entity table.
- **Security (do before publishing):** `CLAUDE.md` in this repo contains the SSH
  add-on password in plaintext. Rotate that password, scrub the file, and note it's
  in git history — publishing requires a history rewrite or a fresh repo.

---

## Verification

1. `go vet` + `go build` in the sandbox; unit tests for the renderer (image
   dimensions per tape width, two-line band split) and date/offset composition.
2. Validate all sentence patterns with the `hassil` package offline (greedy-wildcard
   risk from 2.1).
3. `python -m py_compile` / hassfest-style checks on the integration.
4. Live testing only after your explicit go-ahead: copy files via Samba, rebuild
   add-on, restart HA, then walk through voice phrases with tape loaded.

## Suggested order

Phase 1 → verify Go builds → Phase 2 → validate sentences → Phase 3 → Phase 4 →
your review → deploy. Nothing gets copied to the HAOS box or restarted without your
explicit confirmation at each step.
