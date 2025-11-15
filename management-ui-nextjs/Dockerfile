# Multi-stage build for Next.js Model Management UI
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --legacy-peer-deps

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build Next.js app
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

# Install curl for healthcheck, python3 and requests for download scripts, git for cloning repos, and docker for container management
RUN apk add --no-cache curl python3 py3-requests git docker-cli docker-cli-compose

# Clone grid-image-model-reference repository
RUN git clone https://github.com/aipowergrid/grid-image-model-reference.git /app/grid-image-model-reference

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Add nextjs user to docker group (if it exists) to allow docker socket access
RUN addgroup nextjs docker 2>/dev/null || true

# Copy built assets
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Copy public assets (logo, favicon)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Create cache directory with correct permissions
RUN mkdir -p /app/.next/cache && chown -R nextjs:nodejs /app/.next/cache

# Note: Running as root to allow Docker socket access for container restarts
# This is safe for a local management tool
# USER nextjs

EXPOSE 5000

ENV PORT 5000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]

