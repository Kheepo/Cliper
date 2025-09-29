# Multi-stage build for production optimization
FROM node:18-alpine AS base

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    curl \
    ffmpeg \
    imagemagick \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY requirements.txt ./

# Install Node.js dependencies
RUN npm ci --only=production && npm cache clean --force

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Development stage
FROM base AS development

# Install development dependencies
RUN npm ci && npm cache clean --force
RUN pip3 install --no-cache-dir pytest pytest-asyncio pytest-cov black flake8 mypy

# Copy source code
COPY . .

# Set environment
ENV NODE_ENV=development
ENV PYTHONPATH=/app

# Expose ports
EXPOSE 8000 3000

# Development command
CMD ["npm", "run", "dev"]

# Production stage
FROM base AS production

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Copy source code
COPY --chown=nextjs:nodejs . .

# Create necessary directories
RUN mkdir -p /app/logs /app/uploads /app/temp /app/cache && \
    chown -R nextjs:nodejs /app/logs /app/uploads /app/temp /app/cache

# Set environment
ENV NODE_ENV=production
ENV PYTHONPATH=/app
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 8000

# Production command
CMD ["python3", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Testing stage
FROM development AS testing

# Install additional test dependencies
RUN pip3 install --no-cache-dir coverage pytest-xdist pytest-mock

# Copy test files
COPY tests/ ./tests/

# Run tests
RUN python3 -m pytest tests/ -v --cov=api --cov-report=html --cov-report=term

# Lint and type check
RUN black --check api/ tests/
RUN flake8 api/ tests/
RUN mypy api/

# Build stage for static assets
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build static assets
RUN npm run build

# Nginx stage for serving static files
FROM nginx:alpine AS nginx

# Copy nginx configuration
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/conf.d/ /etc/nginx/conf.d/

# Copy static assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy SSL certificates (if available)
COPY ssl/ /etc/nginx/ssl/

# Health check for nginx
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Expose ports
EXPOSE 80 443

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

# Monitoring stage with additional tools
FROM production AS monitoring

# Install monitoring tools
RUN apk add --no-cache \
    htop \
    iotop \
    netstat-nat \
    tcpdump \
    strace \
    && rm -rf /var/cache/apk/*

# Install Python monitoring packages
RUN pip3 install --no-cache-dir \
    psutil \
    prometheus-client \
    structlog \
    sentry-sdk

# Copy monitoring configuration
COPY monitoring/ ./monitoring/

# Expose monitoring ports
EXPOSE 8000 9090 3000

# Start with monitoring enabled
CMD ["python3", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--access-log", "--log-config", "monitoring/logging.yaml"]