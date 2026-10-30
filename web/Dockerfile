# Web build and runtime images. Run migration/catalog sync as explicit release jobs.
FROM node:22-bookworm-slim AS builder
WORKDIR /app
# Cài full deps trước (cache theo package*.json).
COPY package*.json ./
RUN npm ci
COPY . .
# Biên dịch TS -> dist/, rồi copy thủ công các asset KHÔNG qua tsc:
# views (.ejs), public (.css/.js), schema.sql — đường dẫn runtime là __dirname (=dist/).
RUN npm run build

# ── Image runtime gọn ──────────────────────────────────────────────────────────
FROM node:22-bookworm-slim AS runtime
# Set NODE_ENV=production only behind HTTPS; secrets are required in every mode.
WORKDIR /app
# Chỉ cài dependencies production (bỏ tsx/typescript/@types) -> image nhỏ hơn nhiều.
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=builder /app/dist ./dist
COPY docker-entrypoint.sh ./
# sed: gỡ CR nếu file bị checkout dạng CRLF trên Windows (tránh lỗi "/bin/sh^M").
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 3000

# Readiness checks PostgreSQL; RAG health is monitored separately.
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/ready', {signal: AbortSignal.timeout(4000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

USER node

CMD ["sh", "./docker-entrypoint.sh"]
