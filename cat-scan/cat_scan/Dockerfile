# Build stage
FROM rust:1.82-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

# Copy workspace Cargo files
COPY Cargo.toml Cargo.lock ./
COPY cat_scan/Cargo.toml ./cat_scan/
COPY fake_ssp/Cargo.toml ./fake_ssp/
COPY fake_bidder/Cargo.toml ./fake_bidder/

# Create dummy mains to build dependencies
RUN mkdir -p cat_scan/src fake_ssp/src fake_bidder/src && \
    echo "fn main() {}" > cat_scan/src/main.rs && \
    echo "fn main() {}" > fake_ssp/src/main.rs && \
    echo "fn main() {}" > fake_bidder/src/main.rs
RUN cargo build --release -p cat_scan && rm -rf cat_scan/src

# Copy actual source and embedded assets
COPY cat_scan/src ./cat_scan/src
COPY rtbCatLogo-horizontal.svg.b64 ./rtbCatLogo-horizontal.svg.b64

RUN touch cat_scan/src/main.rs && cargo build --release -p cat_scan

# Runtime stage
FROM debian:bookworm-slim

# Install ca-certificates for AWS SDK and HTTPS
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/cat_scan /usr/local/bin/cat_scan

# Create directories for output
RUN mkdir -p /reports /logs

WORKDIR /workspace

# Default: process local logs file and output to /reports
# Override with docker run arguments
ENTRYPOINT ["cat_scan"]
CMD ["--help"]
