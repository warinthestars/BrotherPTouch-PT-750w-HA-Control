package main

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
	_ "time/tzdata" // embed IANA tz db: Supervisor sets TZ=<host tz> in every
	// add-on container, but the plain-Alpine image has no tzdata package, so Go
	// silently fell back to UTC — labels printed late evening carried tomorrow's
	// date.

	"github.com/golang/freetype/truetype"
	"github.com/ka2n/ptouchgo"
	"golang.org/x/image/font"
	"golang.org/x/image/font/gofont/goregular"
	"golang.org/x/image/math/fixed"
)

const version = "1.1.3"

// ---------------------------------------------------------------------------
// Config (from environment, set by run.sh from add-on options)
// ---------------------------------------------------------------------------

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getIntEnv(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func getFloat64Env(key string, fallback float64) float64 {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.ParseFloat(v, 64); err == nil {
			return n
		}
	}
	return fallback
}

func getBoolEnv(key string, fallback bool) bool {
	if v := os.Getenv(key); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
	}
	return fallback
}

var (
	// e.g. "tcp://192.168.1.100:9100"
	printerAddr   = getEnv("PRINTER_ADDR", "tcp://192.168.1.100:9100")
	tapeWidthMM   = getIntEnv("TAPE_WIDTH_MM", 24)
	fontSize      = getFloat64Env("FONT_SIZE", 40.0) // maximum font size (auto-fit shrinks below this)
	listenAddr    = getEnv("LISTEN_ADDR", ":8080")
	dateFormat    = getEnv("DATE_FORMAT", "Jan 2, 2006") // Go time layout
	timeFormat    = getEnv("TIME_FORMAT", "3:04 PM")     // Go time layout
	autoTapeWidth = getBoolEnv("AUTO_TAPE_WIDTH", true)
	logLevel      = strings.ToLower(getEnv("LOG_LEVEL", "info"))
)

// debugEnabled gates verbose logging: per-request access logs, printer
// dial/status detail, and ptouchgo protocol tracing.
var debugEnabled = logLevel == "debug" || logLevel == "verbose" || logLevel == "trace"

func debugf(format string, v ...any) {
	if debugEnabled {
		log.Printf("DEBUG "+format, v...)
	}
}

// printerMu serializes ALL access to the printer. ptouchgo's RequestStatus
// must not run while a print job is in flight, and the PT-P750W only handles
// one TCP client sanely — so every open→…→close sequence holds this lock.
var printerMu sync.Mutex

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

const printDPI = 180.0 // PT-P750W native resolution

const (
	minFontPt = 6.0
	hPad      = 20 // left+right padding in pixels
)

// printableDotsForTape returns the printable dot height for a given tape width.
// These are physical limits of the PT-P750W print head — the printable area is
// narrower than the physical tape (e.g. 24mm tape → 128 printable dots).
// Formula: (tapeWidthMM / 24) * 128, matching ptouchgo's internal expectations.
func printableDotsForTape(tapeWidthMM int) int {
	return int(float64(tapeWidthMM) / 24.0 * 128.0)
}

// lineSpec is one line of text plus the maximum font size it may use.
type lineSpec struct {
	text  string
	maxPt float64
}

// fitFace returns a font.Face whose total line height (ascent+descent) fits
// within bandPx, starting from maxPt and shrinking. Caller must Close() it.
func fitFace(f *truetype.Font, maxPt float64, bandPx int) font.Face {
	pt := maxPt
	for pt > minFontPt {
		face := truetype.NewFace(f, &truetype.Options{
			Size:    pt,
			DPI:     printDPI,
			Hinting: font.HintingFull,
		})
		m := face.Metrics()
		if (m.Ascent + m.Descent).Ceil() <= bandPx {
			return face
		}
		face.Close()
		pt -= 1
	}
	return truetype.NewFace(f, &truetype.Options{
		Size:    minFontPt,
		DPI:     printDPI,
		Hinting: font.HintingFull,
	})
}

// renderLabel renders 1..2 lines of text into a grayscale image sized for the
// tape. Image width = label length (grows with text), image height = fixed
// printable dot height. With two lines, line 1 gets ~62% of the height and
// line 2 ~38%; each line is auto-fit to its band and centered horizontally.
func renderLabel(lines []lineSpec, tapeWidthMM int) (*image.Gray, error) {
	if len(lines) == 0 || len(lines) > 2 {
		return nil, fmt.Errorf("renderLabel: need 1 or 2 lines, got %d", len(lines))
	}
	heightPx := printableDotsForTape(tapeWidthMM)

	f, err := truetype.Parse(goregular.TTF)
	if err != nil {
		return nil, err
	}

	// Band layout: [top, height] per line
	type band struct{ top, height int }
	var bands []band
	if len(lines) == 1 {
		bands = []band{{0, heightPx}}
	} else {
		h1 := int(float64(heightPx) * 0.62)
		bands = []band{{0, h1}, {h1, heightPx - h1}}
	}

	// Fit a face per line and measure widths
	faces := make([]font.Face, len(lines))
	widths := make([]int, len(lines))
	maxWidth := 0
	for i, ln := range lines {
		faces[i] = fitFace(f, ln.maxPt, bands[i].height)
		d := &font.Drawer{Face: faces[i]}
		widths[i] = d.MeasureString(ln.text).Ceil()
		if widths[i] > maxWidth {
			maxWidth = widths[i]
		}
	}
	defer func() {
		for _, fc := range faces {
			fc.Close()
		}
	}()

	imgWidth := maxWidth + hPad*2
	if imgWidth < 50 {
		imgWidth = 50
	}

	// White canvas
	img := image.NewGray(image.Rect(0, 0, imgWidth, heightPx))
	draw.Draw(img, img.Bounds(), image.White, image.Point{}, draw.Src)

	// Draw each line black, vertically centered in its band, horizontally centered
	for i, ln := range lines {
		m := faces[i].Metrics()
		ascent := m.Ascent.Ceil()
		descent := m.Descent.Ceil()
		baseline := bands[i].top + bands[i].height/2 + (ascent-descent)/2
		x := (imgWidth - widths[i]) / 2

		d := &font.Drawer{
			Dst:  img,
			Src:  image.NewUniform(color.Black),
			Face: faces[i],
			Dot:  fixed.P(x, baseline),
		}
		d.DrawString(ln.text)
	}

	return img, nil
}

// ---------------------------------------------------------------------------
// Printer status
// ---------------------------------------------------------------------------

// error1Labels / error2Labels decode the Brother raster protocol error bitmasks
// (best-effort labels from the PT-P750W raster command reference).
var error1Labels = map[int]string{
	0x01: "No media",
	0x02: "End of media",
	0x04: "Cutter jam",
	0x08: "Weak batteries",
	0x10: "Printer in use",
	0x40: "High-voltage adapter",
}

var error2Labels = map[int]string{
	0x01: "Replace media",
	0x02: "Expansion buffer full",
	0x04: "Communication error",
	0x08: "Communication buffer full",
	0x10: "Cover open",
	0x20: "Overheating",
	0x80: "System error",
}

func decodeErrors(err1, err2 int) []string {
	out := []string{}
	for bit, label := range error1Labels {
		if err1&bit != 0 {
			out = append(out, label)
		}
	}
	for bit, label := range error2Labels {
		if err2&bit != 0 {
			out = append(out, label)
		}
	}
	return out
}

const (
	dialTimeout   = 5 * time.Second
	statusTimeout = 15 * time.Second
	printTimeout  = 90 * time.Second
)

// openPrinter dials the printer with a bounded timeout and sets an absolute
// I/O deadline on the connection. Without this, a sleeping/unreachable
// printer blocks forever in dial or ReadStatus — and since all printer
// access is serialized behind printerMu, one hung connection would wedge
// every subsequent request (this hung HA's config entry setup in the field).
func openPrinter(tapeMM int, ioTimeout time.Duration) (ptouchgo.Serial, error) {
	if !strings.HasPrefix(printerAddr, "tcp://") {
		// non-TCP transports: fall back to the library's own dialer
		return ptouchgo.Open(printerAddr, uint(tapeMM), false)
	}
	addr := strings.TrimPrefix(printerAddr, "tcp://")
	start := time.Now()
	conn, err := net.DialTimeout("tcp", addr, dialTimeout)
	if err != nil {
		debugf("printer dial %s failed after %s: %v", addr, time.Since(start).Round(time.Millisecond), err)
		return ptouchgo.Serial{}, err
	}
	debugf("printer dial %s ok in %s (io deadline %s)", addr, time.Since(start).Round(time.Millisecond), ioTimeout)
	_ = conn.SetDeadline(time.Now().Add(ioTimeout))
	return ptouchgo.Serial{Conn: conn, TapeWidthMM: uint(tapeMM), Debug: debugEnabled}, nil
}

// statusSnapshot opens the printer, reads status, and closes. Holds printerMu.
func statusSnapshot() (*ptouchgo.Status, error) {
	printerMu.Lock()
	defer printerMu.Unlock()

	ser, err := openPrinter(tapeWidthMM, statusTimeout)
	if err != nil {
		return nil, err
	}
	defer ser.Close()

	if err := ser.RequestStatus(); err != nil {
		return nil, err
	}
	st, err := ser.ReadStatus()
	if err != nil {
		debugf("ReadStatus failed: %v", err)
		return nil, err
	}
	debugf("status: model=%s tape=%dmm color=%s err1=%#x err2=%#x phase=%s",
		st.Model, int(st.TapeWidth), st.TapeColor, int(st.Error1), int(st.Error2), st.Phase)
	return st, nil
}

// detectTapeWidthMM asks the printer what tape is loaded. Returns the
// configured default if detection fails or reports an invalid width.
func detectTapeWidthMM() int {
	st, err := statusSnapshot()
	if err != nil {
		log.Printf("tape width detection failed (using configured %dmm): %v", tapeWidthMM, err)
		return tapeWidthMM
	}
	w := int(st.TapeWidth)
	if !ptouchgo.TapeWidth(w).Valid() || w == 0 {
		log.Printf("printer reported invalid tape width %d (using configured %dmm)", w, tapeWidthMM)
		return tapeWidthMM
	}
	return w
}

// ---------------------------------------------------------------------------
// Print pipeline
// ---------------------------------------------------------------------------

type jobOptions struct {
	copies     int
	autocut    bool
	mirror     bool
	halfCut    bool
	chainPrint bool
	highDPI    bool
	feedAmount int
}

func defaultJobOptions() jobOptions {
	return jobOptions{
		copies:     1,
		autocut:    true,
		mirror:     false,
		halfCut:    false,
		chainPrint: false,
		highDPI:    false,
		feedAmount: 10,
	}
}

// runPrintJob sends a rendered image to the printer. Holds printerMu for the
// entire connection lifetime.
func runPrintJob(img image.Image, tapeMM int, opts jobOptions) error {
	// Convert image → ptouchgo raster format
	data, bytesWidth, err := ptouchgo.LoadRawImage(img, ptouchgo.TapeWidth(tapeMM))
	if err != nil {
		return err
	}
	rasterLines := len(data) / bytesWidth
	debugf("raster: %d lines x %d bytes/line, copies=%d autocut=%v mirror=%v halfcut=%v chain=%v highdpi=%v feed=%d",
		rasterLines, bytesWidth, opts.copies, opts.autocut, opts.mirror, opts.halfCut, opts.chainPrint, opts.highDPI, opts.feedAmount)

	// Pack (run-length compress) the raster data
	packedData, err := ptouchgo.CompressImage(data, bytesWidth)
	if err != nil {
		return err
	}

	printerMu.Lock()
	defer printerMu.Unlock()

	ser, err := openPrinter(tapeMM, printTimeout)
	if err != nil {
		return err
	}
	defer ser.Close()

	// Configure printer (mirrors the sequence in the upstream CLI)
	steps := []func() error{
		ser.Reset,
		ser.SetRasterMode,
		func() error { return ser.SetPrintProperty(rasterLines) },
		func() error { return ser.SetPrintMode(opts.autocut, opts.mirror) },
		func() error {
			return ser.SetExtendedMode(
				opts.halfCut,        // pt750halfcut
				!opts.chainPrint,    // noChainprint
				false,               // specialTapeDisableCut
				opts.highDPI,        // highDPI
				false,               // noClearBuffer
			)
		},
		func() error { return ser.SetFeedAmount(opts.feedAmount) },
		func() error { return ser.SetCompressionModeEnabled(true) },
	}
	if opts.copies > 1 && opts.autocut {
		steps = append(steps, func() error { return ser.SetAutocutPerPagesForPTP750W(1) })
	}
	for _, step := range steps {
		if err := step(); err != nil {
			return err
		}
	}

	// Send each copy as a page: FF (Print) between pages, ^Z (PrintAndEject) last
	for i := 0; i < opts.copies; i++ {
		if err := ser.SendImage(packedData); err != nil {
			return err
		}
		if i < opts.copies-1 {
			if err := ser.Print(); err != nil {
				return err
			}
		} else {
			if err := ser.PrintAndEject(); err != nil {
				return err
			}
		}
	}

	ser.Reset() // best-effort cleanup; ignore error
	return nil
}

// ---------------------------------------------------------------------------
// HTTP: /print
// ---------------------------------------------------------------------------

type dateSpec struct {
	OffsetDays  int `json:"offset_days"`
	OffsetWeeks int `json:"offset_weeks"`
}

type printRequest struct {
	Text  string    `json:"text"`
	Date  *dateSpec `json:"date,omitempty"`
	Time  bool      `json:"time,omitempty"`
	Line2 string    `json:"line2,omitempty"` // explicit second line; wins over date/time

	Copies     int      `json:"copies,omitempty"`
	FontSize   float64  `json:"font_size,omitempty"`
	Autocut    *bool    `json:"autocut,omitempty"`
	Mirror     *bool    `json:"mirror,omitempty"`
	HalfCut    *bool    `json:"half_cut,omitempty"`
	ChainPrint *bool    `json:"chain_print,omitempty"`
	HighDPI    *bool    `json:"high_dpi,omitempty"`
	FeedAmount *int     `json:"feed_amount,omitempty"`
}

type printResponse struct {
	Status      string `json:"status"`
	Text        string `json:"text"`
	Line2       string `json:"line2,omitempty"`
	Copies      int    `json:"copies"`
	TapeWidthMM int    `json:"tape_width_mm"`
}

// composeLine2 builds the second label line from the request's date/time
// fields. Returns "" when no second line was requested.
func composeLine2(req *printRequest, now time.Time) string {
	if req.Line2 != "" {
		return req.Line2
	}
	parts := []string{}
	if req.Date != nil {
		d := now.AddDate(0, 0, req.Date.OffsetDays+req.Date.OffsetWeeks*7)
		parts = append(parts, d.Format(dateFormat))
	}
	if req.Time {
		parts = append(parts, now.Format(timeFormat))
	}
	out := ""
	for i, p := range parts {
		if i > 0 {
			out += " "
		}
		out += p
	}
	return out
}

func (req *printRequest) toJobOptions() jobOptions {
	opts := defaultJobOptions()
	if req.Copies > 1 {
		opts.copies = req.Copies
	}
	if req.Autocut != nil {
		opts.autocut = *req.Autocut
	}
	if req.Mirror != nil {
		opts.mirror = *req.Mirror
	}
	if req.HalfCut != nil {
		opts.halfCut = *req.HalfCut
	}
	if req.ChainPrint != nil {
		opts.chainPrint = *req.ChainPrint
	}
	if req.HighDPI != nil {
		opts.highDPI = *req.HighDPI
	}
	if req.FeedAmount != nil && *req.FeedAmount >= 0 {
		opts.feedAmount = *req.FeedAmount
	}
	return opts
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, map[string]string{"error": msg})
}

func handlePrint(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var req printRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON: "+err.Error())
		return
	}
	if req.Text == "" {
		writeError(w, http.StatusBadRequest, "text field is required")
		return
	}
	if req.Copies > 20 {
		writeError(w, http.StatusBadRequest, "copies must be 20 or fewer")
		return
	}

	line2 := composeLine2(&req, time.Now())
	opts := req.toJobOptions()

	tapeMM := tapeWidthMM
	if autoTapeWidth {
		tapeMM = detectTapeWidthMM()
	}

	maxPt := fontSize
	if req.FontSize > 0 {
		maxPt = req.FontSize
	}

	lines := []lineSpec{{text: req.Text, maxPt: maxPt}}
	if line2 != "" {
		lines = append(lines, lineSpec{text: line2, maxPt: maxPt})
	}

	log.Printf("print request: %q line2=%q copies=%d tape=%dmm", req.Text, line2, opts.copies, tapeMM)

	img, err := renderLabel(lines, tapeMM)
	if err != nil {
		log.Printf("render error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	if err := runPrintJob(img, tapeMM, opts); err != nil {
		log.Printf("print error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	log.Printf("printed ok: %q line2=%q x%d", req.Text, line2, opts.copies)
	writeJSON(w, http.StatusOK, printResponse{
		Status:      "printed",
		Text:        req.Text,
		Line2:       line2,
		Copies:      opts.copies,
		TapeWidthMM: tapeMM,
	})
}

// ---------------------------------------------------------------------------
// HTTP: /status
// ---------------------------------------------------------------------------

type statusResponse struct {
	Online       bool     `json:"online"`
	Model        string   `json:"model,omitempty"`
	Battery      string   `json:"battery,omitempty"`
	Error1       int      `json:"error1"`
	Error2       int      `json:"error2"`
	Errors       []string `json:"errors"`
	StatusType   string   `json:"status_type,omitempty"`
	PhaseType    string   `json:"phase_type,omitempty"`
	Phase        string   `json:"phase,omitempty"`
	Notification string   `json:"notification,omitempty"`
	MediaType    string   `json:"media_type,omitempty"`
	TapeColor    string   `json:"tape_color,omitempty"`
	TapeWidthMM  int      `json:"tape_width_mm"`
	TapeLengthMM int      `json:"tape_length_mm"`
	FontColor    string   `json:"font_color,omitempty"`
	Mode         int      `json:"mode"`
	Detail       string   `json:"detail,omitempty"` // set when offline
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	st, err := statusSnapshot()
	if err != nil {
		// Printer unreachable ≠ add-on broken: report online=false with 200
		// so the integration can distinguish printer-down from addon-down.
		writeJSON(w, http.StatusOK, statusResponse{
			Online: false,
			Errors: []string{},
			Detail: err.Error(),
		})
		return
	}

	writeJSON(w, http.StatusOK, statusResponse{
		Online:       true,
		Model:        st.Model.String(),
		Battery:      st.Battery.String(),
		Error1:       int(st.Error1),
		Error2:       int(st.Error2),
		Errors:       decodeErrors(int(st.Error1), int(st.Error2)),
		StatusType:   st.StatusType.String(),
		PhaseType:    st.PhaseType.String(),
		Phase:        st.Phase.String(),
		Notification: st.Notification.String(),
		MediaType:    st.MediaType.String(),
		TapeColor:    st.TapeColor.String(),
		TapeWidthMM:  int(st.TapeWidth),
		TapeLengthMM: st.TapeLength,
		FontColor:    st.FontColor.String(),
		Mode:         st.Mode,
	})
}

// ---------------------------------------------------------------------------
// HTTP: /feed, /test, /config, /health
// ---------------------------------------------------------------------------

func handleFeed(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	tapeMM := tapeWidthMM
	if autoTapeWidth {
		tapeMM = detectTapeWidthMM()
	}

	// A minimal blank label: feeds tape and cuts.
	heightPx := printableDotsForTape(tapeMM)
	img := image.NewGray(image.Rect(0, 0, 50, heightPx))
	draw.Draw(img, img.Bounds(), image.White, image.Point{}, draw.Src)

	if err := runPrintJob(img, tapeMM, defaultJobOptions()); err != nil {
		log.Printf("feed error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "fed"})
}

func handleTest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	tapeMM := tapeWidthMM
	tapeInfo := fmt.Sprintf("%dmm (configured)", tapeMM)
	if st, err := statusSnapshot(); err == nil {
		if w := int(st.TapeWidth); ptouchgo.TapeWidth(w).Valid() && w != 0 {
			tapeMM = w
			tapeInfo = fmt.Sprintf("%dmm %s", w, st.TapeColor.String())
		}
	}

	now := time.Now()
	lines := []lineSpec{
		{text: "PT-P750W " + tapeInfo, maxPt: fontSize},
		{text: now.Format(dateFormat) + " " + now.Format(timeFormat), maxPt: fontSize},
	}

	img, err := renderLabel(lines, tapeMM)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if err := runPrintJob(img, tapeMM, defaultJobOptions()); err != nil {
		log.Printf("test print error: %v", err)
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "printed", "tape": tapeInfo})
}

func handleConfig(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"version":         version,
		"printer_addr":    printerAddr,
		"tape_width_mm":   tapeWidthMM,
		"font_size":       fontSize,
		"date_format":     dateFormat,
		"time_format":     timeFormat,
		"auto_tape_width": autoTapeWidth,
		"log_level":       logLevel,
		"timezone":        os.Getenv("TZ"),
	})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok\n"))
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

// logRequests logs every incoming request with its source address (debug
// level — the HA coordinator polls /status continuously, so this is noisy).
// Useful for diagnosing HA-core→add-on connectivity.
func logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		debugf("%s %s from %s", r.Method, r.URL.Path, r.RemoteAddr)
		next.ServeHTTP(w, r)
	})
}

func main() {
	tzName, _ := time.Now().Zone()
	log.Printf("label-printer %s starting: listen=%s printer=%s tape=%dmm font=%.0fpt auto_tape=%v log=%s tz=%s (%s)",
		version, listenAddr, printerAddr, tapeWidthMM, fontSize, autoTapeWidth, logLevel, os.Getenv("TZ"), tzName)

	http.HandleFunc("/print", handlePrint)
	http.HandleFunc("/status", handleStatus)
	http.HandleFunc("/feed", handleFeed)
	http.HandleFunc("/test", handleTest)
	http.HandleFunc("/config", handleConfig)
	http.HandleFunc("/health", handleHealth)

	if err := http.ListenAndServe(listenAddr, logRequests(http.DefaultServeMux)); err != nil {
		log.Fatalf("fatal: %v", err)
	}
}
