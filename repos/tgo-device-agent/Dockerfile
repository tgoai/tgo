FROM golang:1.22-alpine AS builder

WORKDIR /build

COPY go.mod ./
# COPY go.sum ./  # uncomment when external dependencies are added
# RUN go mod download

COPY . .

RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /tgo-device-agent ./cmd/agent/

# ----
FROM alpine:3.19

RUN apk add --no-cache ca-certificates bash

COPY --from=builder /tgo-device-agent /usr/local/bin/tgo-device-agent

RUN mkdir -p /workspace && \
    adduser -D -h /workspace agent && \
    chown agent:agent /workspace

USER agent
WORKDIR /workspace

ENTRYPOINT ["tgo-device-agent"]
CMD ["--help"]
