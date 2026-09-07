# Single-stage build to avoid permission issues
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Install serve globally
RUN npm install -g serve

# Copy source code
COPY . .

# Build application
RUN npm run build

# Install curl for health checks
RUN apk add --no-cache curl

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start application
CMD ["serve", "-s", "dist", "-l", "3000"]
