# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

# Install build dependencies for TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Build and install TA-Lib C library
RUN wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz \
    && tar xzf ta-lib-0.6.4-src.tar.gz \
    && cd ta-lib-0.6.4 \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime stage ──
FROM python:3.12-slim

# Copy TA-Lib and Python packages from builder
COPY --from=builder /usr/lib/libta_lib* /usr/lib/
COPY --from=builder /usr/include/ta-lib /usr/include/ta-lib/
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . .

# Create data directory
RUN mkdir -p data logs reports

# Default: start web server (port via $PORT env, Railway sets this)
CMD uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8000}
