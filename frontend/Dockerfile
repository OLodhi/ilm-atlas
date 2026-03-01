# --- Dependencies stage ---
FROM node:20-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- Build stage ---
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env var (set via docker-compose build args or CI/CD build-args)
ARG NEXT_PUBLIC_API_URL=https://api.ilmatlas.com
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# --- Runtime stage ---
FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production

# Ensure public dir exists (may be empty)
RUN mkdir -p /app/public

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER node

EXPOSE 3000

CMD ["node", "server.js"]
