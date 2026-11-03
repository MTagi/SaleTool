# Frontend "ABIM Sales Assistant": build the SPA with Vite, then serve static files through nginx.
#
# The build produces plain static files; no environment variables are embedded
# because `src/api/client.js` uses relative paths ("/api/..."). nginx proxies
# /api/ to the backend, keeping UI and API on the same origin without CORS setup.

FROM node:22-alpine AS build

WORKDIR /app

# npm ci requires package-lock.json and installs the exact locked versions.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
