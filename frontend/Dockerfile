# Frontend "ABIM Sales Assistant": build SPA bằng Vite rồi phục vụ tĩnh qua nginx.
#
# Build xong là ra file tĩnh thuần — không có biến môi trường nào nướng vào lúc
# build, vì `src/api/client.js` gọi đường dẫn tương đối ("/api/..."). nginx proxy
# /api/ sang backend nên UI và API cùng origin, không cần cấu hình CORS.

FROM node:22-alpine AS build

WORKDIR /app

# npm ci cần package-lock.json và cài đúng phiên bản đã khoá.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
