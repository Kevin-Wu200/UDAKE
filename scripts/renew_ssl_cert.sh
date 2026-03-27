#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "usage: $0 <domain> <email>" >&2
  exit 1
fi

docker run --rm \
  -p 80:80 \
  -v "$(pwd)/deployment/ssl:/etc/letsencrypt" \
  -v "$(pwd)/deployment/ssl-challenge:/var/www/certbot" \
  certbot/certbot certonly --standalone \
  --non-interactive --agree-tos \
  -m "$EMAIL" -d "$DOMAIN"

echo "cert renewed for $DOMAIN"
