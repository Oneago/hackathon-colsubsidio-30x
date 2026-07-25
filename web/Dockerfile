# syntax=docker/dockerfile:1
# Multi-stage: deps → dev (Vite hot reload) → build → runtime (Nginx).

# ── deps: instala node_modules ───────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# El lock se genera en la arquitectura del desarrollador (arm64) y solo fija ahí
# los binarios nativos opcionales de Rollup; en un host x64 faltaría el suyo y
# `vite build` muere. Se descarta el lock para que npm resuelva el binario de la
# plataforma donde realmente se construye (npm/cli#4828).
RUN rm -f package-lock.json && npm install --include=optional --no-audit --no-fund

# ── dev: servidor Vite con hot reload (código montado en override) ─
FROM node:20-alpine AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ── build: genera el bundle estático de producción ───────────
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ── runtime: Nginx sirve el build (producción) ───────────────
FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
