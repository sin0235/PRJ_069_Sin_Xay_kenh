FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS dependencies

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/sin_creator_os

COPY sin_creator_os/package.json sin_creator_os/package-lock.json sin_creator_os/.npmrc ./
RUN npm ci --no-audit --no-fund

FROM dependencies AS builder
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}

COPY sin_creator_os/next.config.mjs sin_creator_os/postcss.config.mjs sin_creator_os/tsconfig.json ./
COPY sin_creator_os/src ./src
COPY sin_creator_os/public ./public
RUN chmod -R a+rX ./public && npm run build

FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NODE_OPTIONS=--max-old-space-size=384

RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app \
    && chown -R 10001:10001 /app
WORKDIR /app

COPY --from=builder --chown=10001:10001 /app/sin_creator_os/.next/standalone ./
COPY --from=builder --chown=10001:10001 /app/sin_creator_os/.next/static ./.next/static
COPY --from=builder --chown=10001:10001 /app/sin_creator_os/public ./public

USER 10001:10001
EXPOSE 3000
CMD ["node", "server.js"]
