# HTTPS for api.sig.systems (dockerized nginx + Let's Encrypt)

The frontend (`https://installations.sig.systems`) calls the API over HTTPS, and
the `sig_token` cookie is `Secure` (only sent over TLS). So `api.sig.systems`
**must** serve HTTPS. This sets that up with a free Let's Encrypt cert.

Run these **on the production API server** (the one `api.sig.systems` → 173.12.92.73
resolves to), from the `docker/` directory of this repo.

## Prerequisites
- DNS: `api.sig.systems` → this server (already the case).
- Firewall / cloud security group: **ports 80 and 443 open** to the internet.
  - Port 80 is needed for the ACME challenge (and renewals).
- The stack is already running from `docker-compose.yml`.

## 1. Issue the certificate (one time)

certbot runs standalone on port 80, so free it briefly (stop nginx):

```bash
cd docker
docker compose stop nginx

docker run --rm -p 80:80 \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  certbot/certbot certonly --standalone \
  -d api.sig.systems \
  --agree-tos -m admin@sig.systems --no-eff-email -n
```

This writes the cert to `docker/certbot/conf/live/api.sig.systems/`.

## 2. Bring the stack up with HTTPS

```bash
NGINX_CONF=default.ssl.conf \
  docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
```

nginx now listens on 443 (TLS) and redirects 80 → 443. The `certbot` service
auto-renews every 12h via the webroot challenge.

> Tip: put `NGINX_CONF=default.ssl.conf` in `docker/.env` so you don't have to
> pass it on every `docker compose` command.

## 3. Verify

```bash
curl -I https://api.sig.systems/api/v1/health/      # expect 200
```

Then open the app — `https://api.sig.systems` no longer times out and login
works (the Secure cookie is now sent).

## Renewal note
The `certbot` container renews the cert automatically, but **nginx must reload**
to pick up the renewed cert. Add a weekly cron on the host:

```bash
0 3 * * 0  docker exec SIGplatform-nginx nginx -s reload
```

(Cert is valid 90 days and renews at 60, so a weekly reload is plenty.)

## Rollback
To go back to HTTP-only, bring the stack up **without** the SSL overlay / var:

```bash
docker compose -f docker-compose.yml up -d
```
