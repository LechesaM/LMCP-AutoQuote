FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/command-centre/package*.json ./
RUN npm install

COPY frontend/command-centre/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
