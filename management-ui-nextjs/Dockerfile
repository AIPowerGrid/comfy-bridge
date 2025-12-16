# Multi-stage build for Next.js Model Management UI
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies with npm cache mount
COPY package.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --legacy-peer-deps

# Rebuild the source code only when needed
FROM base AS builder
# Install Electron build dependencies if needed
ARG BUILD_ELECTRON=true
RUN if [ "$BUILD_ELECTRON" = "true" ]; then \
        apk add --no-cache \
            python3 \
            make \
            g++ \
            libx11-dev \
            libxext-dev \
            libxss-dev \
            libgconf-2-4 \
            libxtst6 \
            libxrandr2 \
            alsa-lib \
            || echo "Some Electron build dependencies may be missing"; \
    fi
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build Next.js app with cache mount for .next/cache
RUN --mount=type=cache,target=/app/.next/cache \
    npm run build

# Build Electron app (optional - can be skipped if BUILD_ELECTRON=false)
RUN if [ "$BUILD_ELECTRON" = "true" ]; then \
        echo "Building Electron desktop app..." && \
        npm run electron:compile && \
        CSC_IDENTITY_AUTO_DISCOVERY=false npx electron-builder --dir --linux || \
        (echo "Electron build failed or skipped (may require platform-specific dependencies)" && true); \
    else \
        echo "Skipping Electron build (BUILD_ELECTRON=false)"; \
    fi

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

# Install curl for healthcheck, python3 and requests for download scripts, git for cloning repos, and docker for container management
RUN apk add --no-cache curl python3 py3-requests git docker-cli docker-cli-compose

# Clone grid-image-model-reference repository with git cache mount
RUN --mount=type=cache,target=/root/.cache/git \
    git clone --depth 1 https://github.com/aipowergrid/grid-image-model-reference.git /app/grid-image-model-reference

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Add nextjs user to docker group (if it exists) to allow docker socket access
RUN addgroup nextjs docker 2>/dev/null || true

# Copy built assets
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Copy public assets (logo, favicon)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
# Copy Electron build output (if built)
COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist

# Create cache directory with correct permissions
RUN mkdir -p /app/.next/cache && chown -R nextjs:nodejs /app/.next/cache

# Note: Running as root to allow Docker socket access for container restarts
# This is safe for a local management tool
# USER nextjs

EXPOSE 5000

ENV PORT 5000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]

