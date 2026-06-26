# ── Builder stage: compile TA-Lib C library ──
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib C library v0.4.0 (the C library version, different from pip package version)
RUN wget --retry-connrefused --waitretry=5 --read-timeout=20 --timeout=15 \
        https://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib-0.4.0 \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && cd / \
    && rm -rf ta-lib-0.4.0*

# Verify
RUN ldconfig && ls -la /usr/lib/libta_lib*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Runtime stage ──
FROM python:3.12-slim

# Copy TA-Lib runtime libs and Python packages from builder
COPY --from=builder /usr/lib/libta_lib* /usr/lib/
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    LD_LIBRARY_PATH=/usr/lib

# Install runtime tools
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig

WORKDIR /app

# Copy project files
COPY . .

# Runtime directories
RUN mkdir -p data logs reports

# Start web server
CMD uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8000}
