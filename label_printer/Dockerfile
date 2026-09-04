# syntax=docker/dockerfile:1

# ── Stage 1: Build the Go binary ─────────────────────────────────────────────
FROM golang:1.21-alpine AS builder

WORKDIR /build

# git is required by go mod download for VCS-based deps
RUN apk add --no-cache git

# Copy go.mod first; -mod=mod lets Go resolve and write go.sum automatically
# so we don't need to commit a go.sum to the add-on source directory.
COPY go.mod ./
RUN GOFLAGS=-mod=mod go mod download

COPY *.go ./
# CGO_ENABLED=0 → fully static binary, no libc required in the final image
RUN CGO_ENABLED=0 GOOS=linux GOFLAGS=-mod=mod go build -a -ldflags="-s -w" -o label-printer .

# ── Stage 2: Plain Alpine (avoids s6-overlay conflicts in HA base image) ─────
# HA add-ons don't require the HA base image — they just need a running process.
# We read /data/options.json (mounted by Supervisor) directly with jq.
FROM alpine:latest

LABEL \
    io.hass.name="Label Printer" \
    io.hass.description="Print labels on Brother PT-P750W" \
    io.hass.version="1.1.3" \
    io.hass.type="addon" \
    io.hass.arch="aarch64|amd64|armhf|armv7|i386"

RUN apk add --no-cache jq

COPY --from=builder /build/label-printer /usr/local/bin/label-printer
COPY run.sh /run.sh
RUN chmod +x /run.sh /usr/local/bin/label-printer

CMD ["/run.sh"]
