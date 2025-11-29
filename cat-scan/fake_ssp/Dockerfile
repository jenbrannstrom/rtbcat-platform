# Build stage
FROM rust:1.82-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

# Copy workspace Cargo files
COPY Cargo.toml Cargo.lock ./
COPY fake_ssp/Cargo.toml ./fake_ssp/
COPY fake_bidder/Cargo.toml ./fake_bidder/
COPY cat_scan/Cargo.toml ./cat_scan/

# Create dummy mains to build dependencies
RUN mkdir -p fake_ssp/src fake_bidder/src cat_scan/src && \
    echo "fn main() {}" > fake_ssp/src/main.rs && \
    echo "fn main() {}" > fake_bidder/src/main.rs && \
    echo "fn main() {}" > cat_scan/src/main.rs
RUN cargo build --release -p fake_ssp && rm -rf fake_ssp/src

# Copy actual source and build
COPY fake_ssp/src ./fake_ssp/src
RUN touch fake_ssp/src/main.rs && cargo build --release -p fake_ssp

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/fake_ssp /usr/local/bin/fake_ssp

# Create directory for logs
RUN mkdir -p /logs

# No port exposure needed (fake_ssp is an HTTP client, not server)

CMD ["fake_ssp"]
