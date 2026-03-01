# --- Builder stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
