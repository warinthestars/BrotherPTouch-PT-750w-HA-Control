# Changelog

## 1.1.2

- Default `printer_ip` changed to the neutral example `192.168.1.100`
- Added `README.md` / `DOCS.md` / this changelog to the add-on UI

## 1.1.1

- **Fixed:** printer I/O is now strictly bounded (5 s dial, 15 s status, 90 s print deadlines). A sleeping/unreachable printer previously hung requests forever and wedged the serialized request queue
- **Fixed:** `auto_tape_width: false` was impossible to set (`run.sh` boolean parsing)
- **Added:** `log_level` option (`info`/`debug`) — debug logs every HTTP request with source address, printer dial detail, and raw protocol tracing
- `/config` now reports the active `log_level`

## 1.1.0

- Two-line label rendering with per-line auto-fit (`font_size` is now a maximum)
- Expanded `POST /print`: `date` (with day/week offsets for expiry labels), `time`, `line2`, `copies` (1–20, cut separately), per-job `autocut` / `mirror` / `half_cut` / `chain_print` / `high_dpi` / `feed_amount` / `font_size`
- New endpoints: `GET /status`, `GET /config`, `POST /feed`, `POST /test`
- New options: `auto_tape_width` (detect loaded tape before each print), `date_format`, `time_format`
- All printer access serialized behind a mutex

## 1.0.0

- Initial release: `POST /print` (single-line labels) and `GET /health`, driving the PT-P750W over TCP via ptouchgo
