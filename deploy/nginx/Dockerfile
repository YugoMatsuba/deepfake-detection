# syntax=docker/dockerfile:1.4

# --- Build frontend assets ---
FROM node:18-alpine AS fe-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
COPY frontend/ .
RUN npm ci --no-audit --no-fund \
 && npm run build

# --- Nginx to serve frontend and proxy /api ---
FROM nginx:1.27-alpine

# Copy built frontend to the default Nginx web root
COPY --from=fe-build /app/frontend/dist/ /usr/share/nginx/html/

# Replace the default server config
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
