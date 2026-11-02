# The platform admin app, deployed on its own inside EduZone's private network (docs/deploy-admin.md).
# Build from frontend/ (the monorepo root):  docker build -f apps/admin/Dockerfile -t eduzone-admin .
# Run:  docker run -p 3001:3001 -e API_URL=http://<api private address>:8000 eduzone-admin

FROM node:24-alpine AS deps
WORKDIR /app
# Every workspace's package.json so npm ci accepts the shared lockfile; only the admin app's tree is installed.
COPY package.json package-lock.json ./
COPY apps/admin/package.json apps/admin/
COPY apps/web/package.json apps/web/
COPY packages/ui/package.json packages/ui/
COPY packages/lib/package.json packages/lib/
COPY packages/api-client/package.json packages/api-client/
RUN npm ci --workspace @eduzone/admin --include-workspace-root=false --no-audit --no-fund

FROM node:24-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_OUTPUT=standalone
# The installed tree (hoisted and any per-workspace node_modules), then the sources over it.
COPY --from=deps /app ./
COPY packages ./packages
COPY apps/admin ./apps/admin
RUN npm run build -w @eduzone/admin

FROM node:24-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3001 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/apps/admin/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/admin/.next/static ./apps/admin/.next/static
USER node
EXPOSE 3001
CMD ["node", "apps/admin/server.js"]
