-- ─────────────────────────────────────────────────────────────
--  Local production mirror — database + user bootstrap
--
--  Runs FIRST (filename order) on the mirror-db container's first
--  start, before any NN_*.sql production dumps. Creates the three
--  live databases and a single local app user that web/poller use.
--
--  Credentials here MUST match MIRROR_DB_USER / MIRROR_DB_PASSWORD
--  in docker/docker-compose.local.yml (defaults: mirror / mirror).
--  This file contains NO production data and is safe to commit.
-- ─────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS sig_dailylogs  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS slc_schedules  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS sigtools_beta  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'mirror'@'%' IDENTIFIED BY 'mirror';

GRANT ALL PRIVILEGES ON sig_dailylogs.* TO 'mirror'@'%';
GRANT ALL PRIVILEGES ON slc_schedules.* TO 'mirror'@'%';
GRANT ALL PRIVILEGES ON sigtools_beta.* TO 'mirror'@'%';

FLUSH PRIVILEGES;
