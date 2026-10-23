FROM node:20.11.1-alpine AS assets
RUN npm ci && npm run build

FROM php:8.3.30-fpm-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends php8.3-intl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
COPY --from=assets /app/public /var/www/html/public
