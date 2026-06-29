package main

import (
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"log"
	"net/http"
	"os"
	"strconv"

	"github.com/golang/freetype/truetype"
	"github.com/ka2n/ptouchgo"
	"golang.org/x/image/font"
	"golang.org/x/image/font/gofont/goregular"
	"golang.org/x/image/math/fixed"
)

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

var (
	// e.g. "tcp://192.168.1.75:9100"
	printerAddr = getEnv("PRINTER_ADDR", "tcp://192.168.1.75:9100")
	tapeWidthMM = getIntEnv("TAPE_WIDTH_MM", 24)
	fontSize    = getFloat64Env("FONT_SIZE", 40.0)
	listenAddr  = getEnv("LISTEN_ADDR", ":8080")
)

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

const printDPI = 180.0 // PT-P750W native resolution

// printableDotsForTape returns the printable dot height for a given tape width.
// These are physical limits of the PT-P750W print head — the printable area is
// narrower than the physical tape (e.g. 24mm tape → 128 printable dots).
// Formula: (tapeWidthMM / 24) * 128, matching ptouchgo's internal expectations.
func printableDotsForTape(tapeWidthMM int) int {
	return int(float64(tapeWidthMM) / 24.0 * 128.0)
}

// renderLabel renders text into a grayscale image sized for the tape.
// Image width  = variable (label length, grows with text).
// Image height = fixed printable dot height for this tape width.
func renderLabel(text string, tapeWidthMM int, fontSize float64) (*image.Gray, error) {
	heightPx := printableDotsForTape(tapeWidthMM)

	// Parse the bundled Go Regular font (no external font file needed)
	f, err := truetype.Parse(goregular.TTF)
	if err != nil {
		return nil, err
	}
	face := truetype.NewFace(f, &truetype.Options{
		Size:    fontSize,
		DPI:     printDPI,
		Hinting: font.HintingFull,
	})
	defer face.Close()

	// Measure how wide the text will be
	d := &font.Drawer{Face: face}
	textWidthPx := d.MeasureString(text).Ceil()

	const hPad = 20 // left+right padding in pixels
	imgWidth := textWidthPx + hPad*2
	if imgWidth < 50 {
		imgWidth = 50
	}

	// White canvas
	img := image.NewGray(image.Rect(0, 0, imgWidth, heightPx))
	draw.Draw(img, img.Bounds(), image.White, image.Point{}, draw.Src)

	// Vertically center the text.
	// In Go's font.Metrics, Ascent and Descent are both positive.
	metrics := face.Metrics()
	ascent := metrics.Ascent.Ceil()
	descent := metrics.Descent.Ceil()
	// baseline such that text block is centred in heightPx
	baseline := heightPx/2 + (ascent-descent)/2

	// Draw black text
	d.Dst = img
	d.Src = image.NewUniform(color.Black)
	d.Dot = fixed.P(hPad, baseline)
	d.DrawString(text)

	return img, nil
}

// ---------------------------------------------------------------------------
// Print pipeline
// ---------------------------------------------------------------------------

func printLabel(text string) error {
	img, err := renderLabel(text, tapeWidthMM, fontSize)
	if err != nil {
		return err
	}

	// Convert image → ptouchgo raster format
	data, bytesWidth, err := ptouchgo.LoadRawImage(img, ptouchgo.TapeWidth(tapeWidthMM))
	if err != nil {
		return err
	}
	rasterLines := len(data) / bytesWidth

	// Pack (run-length compress) the raster data
	packedData, err := ptouchgo.CompressImage(data, bytesWidth)
	if err != nil {
		return err
	}

	// Open TCP connection to printer
	ser, err := ptouchgo.Open(printerAddr, uint(tapeWidthMM), false)
	if err != nil {
		return err
	}
	defer ser.Close()

	// Configure printer (mirrors the sequence in the upstream CLI)
	steps := []func() error{
		ser.Reset,
		ser.SetRasterMode,
		func() error { return ser.SetPrintProperty(rasterLines) },
		func() error { return ser.SetPrintMode(true, false) },         // autocut=true, mirror=false
		func() error { return ser.SetExtendedMode(false, true, false, false, false) },
		func() error { return ser.SetFeedAmount(10) },
		func() error { return ser.SetCompressionModeEnabled(true) },
		func() error { return ser.SendImage(packedData) },
		ser.PrintAndEject,
	}
	for _, step := range steps {
		if err := step(); err != nil {
			return err
		}
	}

	ser.Reset() // best-effort cleanup; ignore error
	return nil
}

// ---------------------------------------------------------------------------
// HTTP handlers
// ---------------------------------------------------------------------------

type PrintRequest struct {
	Text string `json:"text"`
}

type PrintResponse struct {
	Status string `json:"status"`
	Text   string `json:"text"`
}

func handlePrint(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req PrintRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}
	if req.Text == "" {
		http.Error(w, `{"error":"text field is required"}`, http.StatusBadRequest)
		return
	}

	log.Printf("print request: %q", req.Text)

	if err := printLabel(req.Text); err != nil {
		log.Printf("print error: %v", err)
		http.Error(w, `{"error":"`+err.Error()+`"}`, http.StatusInternalServerError)
		return
	}

	log.Printf("printed ok: %q", req.Text)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(PrintResponse{Status: "printed", Text: req.Text})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok\n"))
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

func main() {
	log.Printf("label-printer starting: listen=%s printer=%s tape=%dmm font=%.0fpt",
		listenAddr, printerAddr, tapeWidthMM, fontSize)

	http.HandleFunc("/print", handlePrint)
	http.HandleFunc("/health", handleHealth)

	if err := http.ListenAndServe(listenAddr, nil); err != nil {
		log.Fatalf("fatal: %v", err)
	}
}
