# ============================================
# Stage 1: Build Frontend (React + Vite)
# ============================================
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

# Copy package files first for better caching
COPY src_frontend/package.json src_frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY src_frontend/ ./

# Build production bundle
RUN npm run build


# ============================================
# Stage 2: Production Image (Python + Nginx)
# ============================================
FROM python:3.12-slim

# Install Nginx and required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/
COPY config.py ./

# Copy .env template (will be overridden by docker-compose volume/env)
COPY .env.docker ./.env

# Copy built frontend from Stage 1
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# Copy Nginx config
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Create log directory
RUN mkdir -p /app/logs

# Copy startup script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose ports: 80 (Nginx), 5001 (Flask - internal)
EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
