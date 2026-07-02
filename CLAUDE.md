PROJECT: Voice-triggered label printing — Brother PT-P750W + Home Assistant + Google Home

STATE UPDATE (2026-07-01): Much of what follows is now historical. The repo
contains a working v1.1.0 implementation: label_printer/ (Go HTTP add-on:
/print with date/time/expiry/copies/per-job options, /status, /feed, /test,
/config, mutex-serialized printer access, two-line auto-fit rendering,
auto tape-width detection) and custom_components/label_printer/ (config flow,
notify/sensor/binary_sensor/number/switch/button platforms, /status polling
coordinator, PrintLabel intent with date/expiry/copies slots, and automatic
installation of its sentence file into config/custom_sentences/en/ — HA does
NOT load sentences bundled inside integrations). See PLAN.md and README.md.
Sentence patterns validated offline with hassil (HA best-match semantics).
NOT yet deployed to the user's HAOS box — deployment requires the user's
explicit confirmation, which still stands. Original context below.

GOAL
Let me say "Hey Google, talk to Home Assistant, print a label that says X" (or speak
into the HA mobile app mic) and have it print on my Brother PT-P750W label printer.
The whole thing needs to be easier to use than just opening the Brother label app.

I have a cloned repo attached/uploaded in this session: github.com/ka2n/ptouchgo
(19 stars, 3 forks, MIT licensed — a real Go driver library, not just a CLI wrapper).
Read it directly before doing anything else.

CONFIRMED FACTS (do not re-derive — verified in a prior session)
- Printer: Brother PT-P750W, connected over WiFi (not USB), static IP 192.168.1.75.
- USB-only tools (ptouch-print/brother_ql) are ruled out — no USB connection exists.
- Brother's own developer manual confirms a real network raster-printing path exists
  over standard TCP, port 9100.
- ptouchgo's library docs (pkg.go.dev) confirm `ptouchgo.Open(address, tapeWidthMM, debug)`
  accepts "tcp://192.168.1.75:9100" as a valid address — this is the right library.
- ptouchgo exposes: Open(), Print(), PrintAndEject(), SendImage(tiffdata []byte),
  ReadStatus(), SetAutocutPerPagesForPTP750W(pages), SetCompressionModeEnabled(),
  SetExtendedMode(), and Status/TapeWidth/TapeColor/BatteryStatusType types.
- SendImage takes pre-rendered TIFF/raster bytes — the library does NOT render text
  to a bitmap itself. Whatever wrapper gets built needs its own text→bitmap→raster
  rendering step before calling SendImage.
- UNVERIFIED / the actual reason this Cowork session exists: the cmd/ptouchgo CLI's
  exact flags were never confirmed — no public docs surfaced, GitHub raw URLs were
  blocked under web_fetch permissions in the prior session. You have the actual repo
  now — read cmd/ptouchgo/*.go directly to settle this. If the CLI already does
  text-to-label rendering with usable flags, that may be simpler than writing a
  custom Go HTTP service against the library. If not (e.g. it only accepts
  pre-made images), favor writing a small custom Go HTTP wrapper directly against
  the ptouchgo library, since that's auditable and avoids depending on an
  unverified CLI interface.
- HA install: Home Assistant OS (HAOS) on a dedicated box/Pi/VM. This means no raw
  shell access to drop files on the host directly — custom HA add-ons need their
  files placed in /addons/local/<slug>/ via Samba, Studio Code Server, or SSH
  (all three are installed on this HA instance: core_samba, a0d7b954_vscode,
  a0d7b954_ssh). I could not write files there myself in the prior session and
  had to stop before drafting the actual add-on.
- Voice path: native Google Assistant→HA routing can't capture free text, only
  fixed phrases tied to entity state. The real path is HA's Assist conversation
  pipeline (reachable via "Hey Google, talk to Home Assistant" or the HA mobile
  app mic icon) using a custom_sentences/en.yaml entry with a {text} slot, which
  CAN capture free dictated text and pass it as a script variable.
- User is open to either: (a) free dictation via Assist, or (b) an input_text
  helper + dashboard button as a fallback if dictation accuracy on label text
  is unreliable.
- Add-on packaging requirements as of Supervisor 2026.04.0 (confirmed from current
  HA developer docs): "add-ons" are now called "apps." build.yaml is deprecated —
  base image must be set via explicit `FROM ghcr.io/home-assistant/base:latest` in
  the Dockerfile (BUILD_FROM is no longer auto-injected). LABEL io.hass.version/
  type/arch required if not using HA's GitHub builder actions. Standard app file
  structure: config.yaml, Dockerfile, run.sh, translations/en.yaml, icon.png, etc.
  config.yaml needs name/version/slug/description/arch (required) plus ports,
  options/schema, map (for config dirs), etc. as needed.
- User explicitly wants printer IP / tape width / etc. to be configurable via env
  vars or during add-on onboarding (the options.json / schema mechanism), NOT
  hardcoded — they're considering publishing this add-on publicly if it works.
- Tape width was being asked about but not yet answered when this session ended —
  ASK THE USER, don't assume (common widths: 6mm/9mm/12mm/18mm/24mm; ptouchgo has
  a TapeWidth type with a Valid() check).

SECURITY NOTE FROM PRIOR SESSION
At one point the prior assistant called ha_get_addon on the SSH add-on and its
plaintext SSH password (now redacted from this file) was echoed back in that
tool result, fully visible in the prior chat transcript. The user should rotate
that SSH password. NOTE: the password previously sat in plaintext in this file,
so it remains in git history until history is rewritten or the repo is
recreated fresh — do that before publishing this repo publicly.

WHAT'S EXPLICITLY NOT DONE YET
No files have been written. No add-on has been created or installed. No HA YAML
has been touched. The prior session stopped specifically to wait for the repo zip
before writing the print-bridge code, and the user has separately asked that
nothing be implemented without their explicit confirmation at each step.

YOUR JOB
1. Read the uploaded ptouchgo repo (especially cmd/ptouchgo) directly to settle
   the open question above.
2. Propose (don't yet build) the concrete architecture: either "use the CLI as-is
   with flags X/Y/Z" or "custom Go HTTP wrapper calling the library directly,"
   with your reasoning given what's actually in the repo.
3. Ask the user for tape width and confirm the printer IP (192.168.1.75) is still
   current before hardcoding anything into examples.
4. Draft the add-on files (config.yaml, Dockerfile, run.sh, the Go source) for
   the user to review.
5. WAIT for explicit user confirmation before installing/placing/running anything
   — this constraint is firm and carries over from the prior session.
6. Give the user copy/paste-ready steps for getting the files into
   /addons/local/<slug>/ via Samba or Studio Code Server, since you likely won't
   have direct filesystem access to their HAOS instance either — confirm what
   tool access you actually have before assuming you can write there directly.
7. Once the add-on is in place (per user confirmation), help with the HA-side
   rest_command / script / custom_sentences wiring for the Assist voice trigger.

Treat the user as a careful, technically capable homelab tinkerer who wants to
understand tradeoffs, not just be handed a black box. They've been pushing back
on unverified claims throughout (rightly) — keep being precise about what's
confirmed vs. assumed, and cite sources/code when you can.