.PHONY: build test lint cover secrets check doctor coverage init paper train
build:
	go build -trimpath -o bin/bitbankpoloniex ./cmd/bitbankpoloniex
test:
	go test -race ./...
	go vet ./...
lint:
	go vet ./...
	test -z "$$(gofmt -l cmd internal)"
	staticcheck ./...
cover:
	go test -race -coverprofile=coverage.out ./...
	go tool cover -func=coverage.out | tail -1
secrets:
	gitleaks detect --config .gitleaks.toml --redact --exit-code 1
check: lint test secrets cover
doctor: build
	./bin/bitbankpoloniex --command doctor
coverage: build
	./bin/bitbankpoloniex --command coverage
init: build
	./bin/bitbankpoloniex --command init
paper: build
	./bin/bitbankpoloniex --command run
train: build
	./bin/bitbankpoloniex --command train --markets 25
