-- =============================================================================
-- ⚠ EJECUCIÓN MANUAL ÚNICAMENTE — NO automatizar, NO correr desde un agente.
--   Solo un humano/DBA con backup previo (scripts/backup_db.py) corre esto,
--   fase por fase, revisando los conteos entre fases.
-- =============================================================================
-- T1 — Multi-tenant foundation: schema changes for inventory tenant scoping.
-- DB: sigtools_beta (MySQL 8, alias "sigtools"). Tenant root = `customer_groups`.
--
-- DESIGN — dos niveles de inventario:
--
--   ArticleGroup (groups): categorías compartidas del cliente (ej: "Cables",
--     "Switches"). Nivel cliente. YA recibe customer_group_id (DIRECT).
--
--   Article (articles): unidad física única y rastreable (asset tracking con
--     stock). Nivel site. Recibe site_id (DERIVED: site -> customer_group).
--     Un artículo ES un ítem físico específico en una ubicación — no es un
--     tipo de catálogo reutilizable entre sites.
--
--   ActivityLog (activity_logs): sigue al artículo. Sin columna nueva —
--     tenant derivado via article -> site -> customer_group (3 niveles, sin
--     redundancia).
--
-- SCOPE DE ESTE SCRIPT:
--   groups        → ADD customer_group_id  (DIRECT, nivel cliente)
--   articles      → ADD site_id            (DERIVED, nivel site)
--   activity_logs → sin cambio de esquema  (deriva via article.site_id)
--
-- WHY raw SQL (not Django migration): los modelos son `managed = False` — Django
-- no posee este esquema. Sin RLS (MySQL); aislamiento es solo app-layer.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- PHASE A — agregar columnas nullable + índices (completamente reversible)
-- -----------------------------------------------------------------------------

-- groups: nivel cliente — customer_group_id directo
ALTER TABLE `groups`
    ADD COLUMN `customer_group_id` BIGINT UNSIGNED NULL,
    ADD INDEX `idx_groups_cg` (`customer_group_id`);

-- articles: nivel site — site_id (tenant se deriva vía site)
ALTER TABLE `articles`
    ADD COLUMN `site_id` BIGINT UNSIGNED NULL,
    ADD INDEX `idx_articles_site` (`site_id`);


-- -----------------------------------------------------------------------------
-- PHASE B — backfill (correr tras Phase A; verificar conteos antes de Phase C)
-- -----------------------------------------------------------------------------

-- groups: backfill al customer_group mínimo como default.
-- La re-asignación real por cliente se hace de forma lazy en onboarding.
SET @default_cg = (SELECT MIN(`id`) FROM `customer_groups`);
UPDATE `groups` SET `customer_group_id` = @default_cg WHERE `customer_group_id` IS NULL;

-- articles: backfill de site_id — el campo `location` es texto libre y NO
-- es un FK a sites. El DBA debe mapear manualmente site_id por artículo
-- consultando el campo location y la tabla sites.
--
-- Consulta de diagnóstico para orientar el mapeo:
--   SELECT a.id, a.sku, a.location, s.id site_id, s.name site_name
--   FROM articles a
--   LEFT JOIN sites s ON LOWER(s.name) LIKE CONCAT('%', LOWER(a.location), '%')
--   ORDER BY a.location;
--
-- Una vez identificados los site_id correctos, ejecutar algo como:
--   UPDATE articles SET site_id = <N> WHERE location = '<texto>';
--
-- Para artículos sin site claro, asignar el site raíz del default_cg:
SET @default_site = (
    SELECT MIN(id) FROM `sites`
    WHERE `customer_group_id` = (SELECT MIN(id) FROM `customer_groups`)
);
-- Catch-all: solo rellena artículos que quedaron sin site tras el mapeo manual.
-- Correr SOLO después de completar el mapeo manual arriba. Inspeccionar antes:
--   SELECT COUNT(*) FROM articles WHERE site_id IS NULL;
UPDATE `articles` SET `site_id` = @default_site WHERE `site_id` IS NULL;


-- -----------------------------------------------------------------------------
-- PHASE C — enforce NOT NULL (correr SOLO tras Phase B con cero NULLs)
-- -----------------------------------------------------------------------------
-- ONE-WAY DOOR. Verificar antes:
--   SELECT 'groups'   tbl, COUNT(*) n FROM `groups`   WHERE customer_group_id IS NULL
--   UNION ALL
--   SELECT 'articles' tbl, COUNT(*) n FROM `articles` WHERE site_id IS NULL;
-- Ambos deben devolver 0 antes de correr esto.

ALTER TABLE `groups`    MODIFY `customer_group_id` BIGINT UNSIGNED NOT NULL;
ALTER TABLE `articles`  MODIFY `site_id`            BIGINT UNSIGNED NOT NULL;


-- ROLLBACK (deshacer Phase A / C):
--   ALTER TABLE `groups`    DROP COLUMN `customer_group_id`;  -- índice cae con la columna
--   ALTER TABLE `articles`  DROP COLUMN `site_id`;
-- activity_logs no tiene columna nueva — nada que revertir.
