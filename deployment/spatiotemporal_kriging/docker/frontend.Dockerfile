FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json /app/
RUN npm ci && npm install --no-save esbuild

COPY . /app
RUN npm run build:prod

FROM nginx:1.27-alpine
COPY deployment/spatiotemporal_kriging/nginx/frontend_static.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/apps/frontend/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
