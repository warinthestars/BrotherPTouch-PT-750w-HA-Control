# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The add-on (`label_printer/`) and the integration (`custom_components/label_printer/`)
are versioned together; component-specific notes are labeled **Add-on** or **Integration**.

## [1.1.2] - 2026-07-02

### Changed
- **Add-on:** default `printer_ip` is now the neutral example `192.168.1.100`
  (was a development machine's address). Set your own printer's IP during onboarding.
- Documentation overhaul for public release: rewritten README with full
  start-to-finish walkthrough, add-on `DOCS.md`/`README.md`/`CHANGELOG.md`
  (rendered in the add-on UI tabs), option descriptions for all current options,
  MIT `LICENSE` file, this changelog.

## [1.1.1] - 2026-07-02

### Fixed
- **Integration:** `PrintLabel` intent registration moved into
  `intent.async_setup_intents()`. HA discovers any `intent.py` inside an
  integration as an intent platform and requires that entry point — the
  previous manual registration crashed with
  `AttributeError: ... has no attribute 'async_setup_intents'`.
- **Add-on:** printer I/O is now strictly bounded (5 s dial timeout, 15 s
  status deadline, 90 s print deadline). Previously a sleeping or unreachable
  PT-P750W blocked `ReadStatus` forever and — because printer access is
  serialized — wedged every subsequent request, hanging HA's config entry
  setup indefinitely.
- **Integration:** config entry setup now gates only on the *add-on* being
  reachable (via `GET /config`, which never touches the printer). A powered-off
  printer no longer blocks setup; it is reported through the Online sensor.
- **Integration:** the first status refresh is non-blocking; entities appear
  immediately and populate on the next successful poll.
- **Integration:** config flow logs the exact connection failure
  (DNS / refused / timeout) instead of a generic "cannot connect", normalizes
  the host input (strips `http://`, trailing slashes, whitespace), and defaults
  to `local-label-printer` (the add-on's internal hostname).
- **Add-on:** `run.sh` boolean option parsing — jq's `//` operator treats
  `false` as empty, which made `auto_tape_width: false` impossible to set.

### Added
- **Add-on:** `log_level` option (`info`/`debug`). Debug adds per-request
  access logs with source addresses, printer dial timing and results, status
  decode detail, and raw ptouchgo protocol tracing.
- **Add-on:** `GET /config` now reports the active `log_level`.
- **Integration:** shorter, differentiated HTTP timeouts (20 s status/config,
  120 s print) so a slow add-on can never stall Home Assistant startup.

## [1.1.0] - 2026-07-01

### Added
- **Add-on:** two-line label rendering — line 1 gets ~62 % of the printable
  height, line 2 ~38 %, both auto-fit (the `font_size` option is now a
  maximum, not a fixed size) and horizontally centered.
- **Add-on:** expanded `POST /print` body: `date` (with `offset_days` /
  `offset_weeks` for expiry labels), `time`, `line2`, `copies` (1–20, each cut
  separately), and per-job `font_size`, `autocut`, `mirror`, `half_cut`,
  `chain_print`, `high_dpi`, `feed_amount`.
- **Add-on:** new endpoints: `GET /status` (live printer status: model,
  battery, errors, media type, tape color/width/length, phase), `GET /config`
  (effective configuration), `POST /feed` (feed & cut), `POST /test`
  (test label with detected tape info).
- **Add-on:** `auto_tape_width` option — reads the loaded tape width from the
  printer before each print, eliminating tape-size mismatch errors.
- **Add-on:** `date_format` / `time_format` options (Go time layouts).
- **Add-on:** all printer access serialized behind a mutex so status polls can
  never collide with an in-flight print job.
- **Integration:** status-polling coordinator plus a full entity suite:
  9 sensors (tape width/color, text color, media type, battery, model, error,
  phase, status), Online and Problem binary sensors, Font size and Feed amount
  numbers, Auto cut / Mirror / Half cut / Chain printing / High DPI switches,
  and Feed & cut / Test print buttons.
- **Integration:** Assist sentence patterns for dates ("with today's date"),
  time, expiry offsets ("expiring in 5 days", "good for in 2 weeks"), and
  copies ("print 3 labels saying …"), validated offline against hassil with
  HA's best-match semantics.
- **Integration:** automatic installation of the sentence file into
  `config/custom_sentences/en/` with a managed-file marker (HA does not load
  sentence files bundled inside integrations) and a conversation reload, so
  voice works without a restart.
- **Integration:** options flow for the status poll interval.

### Changed
- **Integration:** `notify.send_message`'s optional `title` now prints as the
  smaller second label line.

## [1.0.0] - 2026-06-29

### Added
- Initial release: Go HTTP add-on (`POST /print` for single-line labels,
  `GET /health`) driving the Brother PT-P750W over TCP port 9100 via
  [ptouchgo](https://github.com/ka2n/ptouchgo), plus a Home Assistant custom
  integration with a config flow, a `notify.label_printer` entity, and a
  `PrintLabel` Assist intent.

[1.1.2]: https://github.com/warinthestars/BrotherPTouch-PT-750w-HA-Control/releases/tag/v1.1.2
[1.1.1]: https://github.com/warinthestars/BrotherPTouch-PT-750w-HA-Control/releases/tag/v1.1.1
[1.1.0]: https://github.com/warinthestars/BrotherPTouch-PT-750w-HA-Control/releases/tag/v1.1.0
[1.0.0]: https://github.com/warinthestars/BrotherPTouch-PT-750w-HA-Control/releases/tag/v1.0.0
