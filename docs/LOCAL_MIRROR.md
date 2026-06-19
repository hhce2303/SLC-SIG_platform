# Local Production Mirror

Cómo levantar un entorno local que es un **espejo idéntico de producción**: mismas
versiones de imagen, mismos settings (`DJANGO_ENV=production`, `DEBUG=False`) y las
tres bases de datos vivas con esquema + datos reales — sin depender de las MySQL de
producción en tiempo de ejecución.

## Qué replica

| Pieza | Producción | Espejo local |
|---|---|---|
| Motor DB | **MariaDB 10.11** (temporal; revierte a MySQL después) | `mariadb:10.11` (pinned, idéntico) |
| DB `default` | `sig_dailylogs` @ `72.167.56.142` | `sig_dailylogs` @ contenedor `mirror-db` |
| DB `schedules` | `slc_schedules` @ `192.168.101.135` | `slc_schedules` @ `mirror-db` |
| DB `sigtools` | `sigtools_beta` @ `72.167.56.142` (solo lectura) | `sigtools_beta` @ `mirror-db` |
| Settings | `production` / `DEBUG=False` | igual (paridad real) |
| Transporte | HTTPS (cert CA real) | HTTPS (cert self-signed, ver abajo) |
| redis / nginx / web / poller | iguales | iguales |

> **Motor de DB:** producción corre **MariaDB 10.11 temporalmente** y volverá a MySQL más
> adelante. El espejo usa `mariadb:10.11` para coincidir. ⚠️ La migración
> `installations.0008_mariadb_uuid_and_pending_state` usa el tipo nativo `uuid` (solo
> MariaDB 10.7+) y **fallará cuando producción vuelva a MySQL** — hay que volverla
> condicional por vendor antes de ese cambio.

> La conexión `inventory` (`Daily` @ LAN) **no se replica**: el `InventoryRouter` está
> comentado, así que la app `inventory` usa `default`. Si algún día se activa, se añade
> una cuarta DB al bootstrap.

## Las tres diferencias permitidas (regla de espejo)

El overlay [`docker/docker-compose.local.yml`](../docker/docker-compose.local.yml) aplica
exactamente los 3 cambios permitidos frente a producción:

1. **Hosts de DB** → apuntan al contenedor `mirror-db` en vez de los hosts remotos.
2. **Credenciales** → un único usuario local `mirror`/`mirror` con acceso a las 3 DBs.
3. `ALLOWED_HOSTS` → ya incluye `localhost`/`127.0.0.1` en `.env`.

`DEBUG` y `DJANGO_ENV` se mantienen en `production` a propósito, para detectar errores
reales de producción en local.

---

## Paso 1 — Generar los dumps de producción

Ejecuta esto **desde una máquina con acceso a las MySQL de producción** (no desde el
contenedor). Te pedirá la contraseña de cada DB. Los archivos van directo a
`docker/init-db/` con prefijo numérico para que importen en orden tras el bootstrap.

```bash
# 1) sig_dailylogs (DB principal)
mysqldump -h 72.167.56.142 -P 3306 -u sig_dailylogs_db_user -p \
  --single-transaction --routines --triggers --no-tablespaces \
  --set-gtid-purged=OFF --databases sig_dailylogs \
  > docker/init-db/10_sig_dailylogs.sql

# 2) slc_schedules (LAN)
mysqldump -h 192.168.101.135 -P 3306 -u app_user -p \
  --single-transaction --routines --triggers --no-tablespaces \
  --set-gtid-purged=OFF --databases slc_schedules \
  > docker/init-db/20_slc_schedules.sql

# 3) sigtools_beta
mysqldump -h 72.167.56.142 -P 3306 -u sigtools_beta_db_user -p \
  --single-transaction --routines --triggers --no-tablespaces \
  --set-gtid-purged=OFF --databases sigtools_beta \
  > docker/init-db/30_sigtools_beta.sql
```

### Neutralizar los `DEFINER`

Los dumps con `--routines`/`--triggers`/vistas incluyen `DEFINER=\`user\`@\`host\``
que apuntan a usuarios de producción inexistentes en local; la importación fallaría.
Quítalos:

```powershell
# PowerShell (Windows)
Get-ChildItem docker/init-db/*.sql | ForEach-Object {
  (Get-Content $_ -Raw) -replace 'DEFINER=`[^`]+`@`[^`]+`','' | Set-Content $_ -Encoding utf8
}
```
```bash
# bash / git-bash
sed -i -E 's/DEFINER=`[^`]+`@`[^`]+`//g' docker/init-db/*.sql
```

> Estos `.sql` contienen datos de producción y **están en `.gitignore`** — nunca se
> commitean. Solo `00_init_databases.sql` (bootstrap, sin datos) es versionado.

---

## Paso 2 — Certificado HTTPS (una sola vez)

`production.py` fuerza cookies `Secure` + HSTS, que solo funcionan sobre HTTPS. El overlay
[`docker/docker-compose.ssl.yml`](../docker/docker-compose.ssl.yml) hace que nginx termine
TLS igual que producción, usando un cert self-signed en `docker/certs/`:

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout docker/certs/localhost.key -out docker/certs/localhost.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:api.sig.systems,IP:127.0.0.1"
# En git-bash (Windows) antepón MSYS_NO_PATHCONV=1 para que -subj no se corrompa.
```

## Paso 3 — Levantar el espejo

```bash
# Si venías de un overlay anterior con otro volumen, límpialo primero:
docker compose -f docker/docker-compose.yml -f docker/docker-compose.local.yml -f docker/docker-compose.ssl.yml down -v --remove-orphans

# Arranque (la PRIMERA vez importa los dumps; puede tardar varios minutos)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.local.yml -f docker/docker-compose.ssl.yml up -d
```

Orden de arranque: `mirror-db` importa `00_init_databases.sql` → `10/20/30_*.sql`, queda
`healthy` (el healthcheck usa **TCP**, así no se marca listo mientras importa), y entonces
`web` corre `entrypoint.sh` (migrate + collectstatic) **contra el espejo local**. Esto
convierte al espejo en el lugar seguro para validar migraciones pendientes (p. ej. la `0008`
con el tipo `uuid` de MariaDB) antes de aplicarlas en producción.

> El import de dumps grandes necesita `--max-allowed-packet=512M` (ya en el overlay) o aborta
> con *"Server has gone away"*. El primer arranque puede tardar varios minutos; `web` espera
> al healthcheck TCP de `mirror-db`.

## Paso 4 — Verificar

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.local.yml -f docker/docker-compose.ssl.yml ps

# Health sobre HTTPS (cert self-signed → -k) y redirect HTTP→HTTPS (301)
curl -sk https://localhost/api/v1/health/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/v1/health/

# Confirmar que las 3 DBs tienen tablas/datos
docker exec SIGplatform-mirror-db sh -c 'mariadb -u root -prootpass -e "SELECT table_schema, COUNT(*) tables FROM information_schema.tables WHERE table_schema IN (\"sig_dailylogs\",\"slc_schedules\",\"sigtools_beta\") GROUP BY table_schema;"'
```

## Re-sembrar (refrescar datos desde prod)

Los dumps solo importan en volumen vacío. Para refrescar:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.local.yml -f docker/docker-compose.ssl.yml down -v   # borra el volumen mirror_db_data
# (regenera los dumps del Paso 1 si quieres datos más nuevos)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.local.yml -f docker/docker-compose.ssl.yml up -d
```

## Notas

- Puerto host de la DB: `3310` (override con `MIRROR_DB_PORT` en `docker/.env`). El puerto
  interno entre contenedores siempre es `3306`.
- Credenciales locales: `mirror`/`mirror` (override con `MIRROR_DB_USER`/`MIRROR_DB_PASSWORD`
  en `docker/.env`; si los cambias, ajusta también `docker/init-db/00_init_databases.sql`).
- `sigtools` es solo-lectura por el `SigtoolsRouter` (`allow_migrate` → `False`): el espejo
  importa sus tablas pero Django nunca las migra, igual que en producción.
