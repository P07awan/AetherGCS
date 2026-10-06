# Multi-stage Dockerfile for AetherGCS Frontend

# Stage 1: Build React static assets
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using yarn
COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install

# Copy frontend source code
COPY . .

# Build argument for backend URL (empty string enables default relative proxying via Nginx)
ARG REACT_APP_BACKEND_URL=""
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL} \
    CI=false

RUN yarn build

# Stage 2: Serve with lightweight Nginx
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/build /usr/share/nginx/html

# Copy custom Nginx configuration with reverse proxy & WebSocket support
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
