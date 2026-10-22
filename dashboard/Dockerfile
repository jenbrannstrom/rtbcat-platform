FROM node:24.22.1-bookworm-slim@sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205 AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

COPY package.json package-lock.json* ./
COPY vendor ./vendor
RUN npm ci

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Version passed as build arg, exposed to Next.js at build time
ARG APP_VERSION=0.0.0
ARG GIT_SHA=unknown
ARG RELEASE_VERSION=0.0.0
ENV NEXT_PUBLIC_APP_VERSION=${APP_VERSION}
ENV NEXT_PUBLIC_GIT_SHA=${GIT_SHA}
ENV NEXT_PUBLIC_RELEASE_VERSION=${RELEASE_VERSION}
ENV NEXT_TELEMETRY_DISABLED=1

# OAuth2 Proxy mode - disables API rewrites so requests go through nginx
ARG OAUTH2_PROXY_MODE=false
ARG API_HOST=localhost
ENV OAUTH2_PROXY_MODE=${OAUTH2_PROXY_MODE}
ENV API_HOST=${API_HOST}

RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
