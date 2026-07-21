# Esquema — `camera_models` (sigtools_beta)

Referencia canónica de las columnas de la tabla `camera_models`, usada por automatización, imports y
cualquier código que lea/escriba specs de fábrica de cámaras. Esta tabla vive en la base externa
`sigtools_beta` (alias de conexión Django `"sigtools"`, ver `config/settings/base.py:168-172`), que es
**legacy y read-only para Django**: `SigtoolsRouter.allow_migrate` (`config/db_router.py:108-113`) bloquea
cualquier migración contra esa app/DB. Todo el acceso pasa por SQL crudo vía
`connections["sigtools"].cursor()` (ver `apps/installations/selectors.py`) o por el ORM sobre el modelo
`managed=False` `apps.sigtools.models.CameraModel`.

## Columnas originales (preexistentes, no gestionadas por este proyecto)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `BIGINT` (PK) | |
| `camera_type_id` | `BIGINT` (FK → `camera_types.id`) | Sin constraint real (`db_constraint=False`) |
| `camera_brand_id` | `BIGINT` (FK → `camera_brands.id`) | Sin constraint real |
| `name` | `VARCHAR(255)` | Único |
| `created_at` / `updated_at` | `DATETIME` | |

## Columnas de spec de fábrica (agregadas por este proyecto)

Agregadas manualmente vía `python manage.py add_camera_spec_columns --yes`
(`apps/sigtools/management/commands/add_camera_spec_columns.py`) — **no** vía migración Django (el router
las bloquearía). Ver ese comando para el DDL exacto y la verificación de idempotencia contra
`INFORMATION_SCHEMA.COLUMNS`.

| Columna | Tipo | Notas |
|---|---|---|
| `rango_lente_mm` | `JSON NULL` | `[min, max]` en mm de distancia focal. Ej. `[2.8, 12]`. `null` si el modelo aún no tiene spec cargado. |
| `rango_fov_grados` | `JSON NULL` | `[min, max]` en grados de campo de visión. Ej. `[104, 29]`. |
| `lens_type` | `VARCHAR(20) NULL` | `"fixed"` \| `"varifocal"` \| `"hybrid"`. |
| `poe_watts` | `FLOAT NULL` | Consumo PoE nominal de fábrica. |
| `bandwidth_mbps` | `FLOAT NULL` | Ancho de banda estimado de fábrica. |

Estos 5 campos reflejan exactamente las claves que ya consume
`apps/installations/catalog_enrichment.py::enrich_camera_item` — si vienen pobladas desde la DB, tienen
prioridad sobre el fallback hardcodeado por *subtype* en `DEFAULT_CAM_SPECS`. Si están en `null`, el
enrichment cae automáticamente al default del subtype (comportamiento sin cambios para modelos aún no
completados).

## Dónde se editan

- **Admin Django**: `CameraModelAdmin` en `apps/sigtools/admin.py` — única excepción al patrón
  `ReadOnlyAdminMixin` de ese admin site, habilitada solo para estos 5 campos.
- **Lectura**: `apps/installations/selectors.py` — `_compute_camera_model_catalog()`,
  `get_site_camera_models()`, `get_site_switch_models()`.
- **Caché**: ver `apps/core/cache_utils.py` — catálogo general cacheado bajo
  `"inst:catalog:camera_model_catalog:v3"` (`TTL_CATALOG` = 600s); catálogos por sitio bajo
  `f"inst:catalog:site_camera_models:{site_id}"`. Ambas keys se invalidan al guardar un spec desde el admin
  o al insertar/eliminar cámaras de un sitio (ver `apps/installations/services.py`).

## Import masivo (futuro)

Aún no implementado — cuando existan datos de fábrica en CSV/Excel/JSON, agregar un management command de
upsert (por `camera_model_id` o por `brand`+`name`) que escriba estas mismas 5 columnas.
