APP_NAME := tgo-device-agent
VERSION  := 1.0.0
GO       := go
GOFLAGS  := -ldflags="-s -w -X main.version=$(VERSION)"
BIN_DIR  := bin

.PHONY: all build clean vet test run

all: build

build:
	@mkdir -p $(BIN_DIR)
	$(GO) build $(GOFLAGS) -o $(BIN_DIR)/$(APP_NAME) ./cmd/agent/

build-linux:
	@mkdir -p $(BIN_DIR)
	GOOS=linux GOARCH=amd64 $(GO) build $(GOFLAGS) -o $(BIN_DIR)/$(APP_NAME)-linux-amd64 ./cmd/agent/

build-darwin:
	@mkdir -p $(BIN_DIR)
	GOOS=darwin GOARCH=arm64 $(GO) build $(GOFLAGS) -o $(BIN_DIR)/$(APP_NAME)-darwin-arm64 ./cmd/agent/

vet:
	$(GO) vet ./...

test:
	$(GO) test -v -race ./...

clean:
	rm -rf $(BIN_DIR)

run: build
	$(BIN_DIR)/$(APP_NAME) --server localhost:9876 --bind-code TEST123 --log-level debug

docker-build:
	docker build -t $(APP_NAME):$(VERSION) .
