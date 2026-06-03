# Auditoría de Base de Datos — sigtools_beta
**Período auditado:** 2026-05-01 → 2026-05-31
**Elaborado:** 2026-05-31
**Audiencia:** DBAs / DevOps
**Propósito:** Evidencia auditable de cambios + guía de migración a producción
**Base de datos:** `sigtools_beta` (alias Django: `sigtools`)
**Motor:** MySQL / InnoDB / utf8mb4
**Mecanismo DDL:** Raw SQL — todas las tablas son `managed = False` en Django

---

## SECCIÓN 1 — Inventario de Cambios

### 1.1 Cronología

| Fecha | Tabla | Tipo de cambio |
|-------|-------|----------------|
| 2026-05-10 | `activity_logs` | CREATE |
| 2026-05-10 | `companies` | CREATE |
| 2026-05-10 | `articles` | CREATE |
| 2026-05-10 | `groups` | CREATE |
| 2026-05-12 | `layers` | CREATE |
| 2026-05-13 | `refresh_tokens` | CREATE |
| 2026-05-15 | `devices` | CREATE |
| 2026-05-15 | `device_positions` | CREATE |
| 2026-05-15 | `installation_devices_link` | CREATE |
| 2026-05-15 | `canvas_positions` | CREATE |
| 2026-05-15 | `device_hierarchy` | CREATE |
| 2026-05-15 | `device_order` | CREATE |
| 2026-05-15 | `site_images` | CREATE |
| 2026-05-26 | `cameras` | ALTER — columnas `device_id`, `canvas_instance_id` + índice `uq_cam_instance` + FK |
| 2026-05-26 | `other_devices` | ALTER — columnas `device_id`, `canvas_instance_id` + índice `uq_od_instance` + FK |
| 2026-05-28 | `project_sites` | CREATE |
| 2026-05-29 | `app_roles` | DROP + CREATE — migración de PK `CHAR(36)` UUID → `INT UNSIGNED` AUTO_INCREMENT |
| 2026-05-29 | `permissions` | DROP + CREATE — migración de PK `CHAR(36)` UUID → `INT UNSIGNED` AUTO_INCREMENT |
| 2026-05-29 | `role_permissions` | DROP + CREATE — nuevas FK constraints + PK compuesto |
| 2026-05-29 | `user_app_roles` | DROP + CREATE — columna `role_id` de `CHAR(36)` → `INT UNSIGNED` |

---

### 1.2 Tablas nuevas

#### `companies`
Catálogo de empresas clientes del sistema de inventario.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20)` | NO | — | PK, AUTO_INCREMENT |
| `name` | `varchar(255)` | NO | — | UNIQUE |
| `description` | `text` | YES | NULL | — |
| `logo_url` | `text` | YES | NULL | — |
| `created_at` | `timestamp` | NO | `current_timestamp()` | — |

**FKs entrantes:** `groups.company_id`

---

#### `groups`
Grupos de artículos dentro de una empresa para clasificación de inventario.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20)` | NO | — | PK, AUTO_INCREMENT |
| `name` | `varchar(255)` | NO | — | — |
| `description` | `text` | YES | NULL | — |
| `icon_name` | `text` | YES | NULL | — |
| `color` | `text` | YES | NULL | — |
| `company_id` | `bigint(20)` | YES | NULL | FK → `companies(id)` |

**FKs:** `company_id → companies(id)` RESTRICT/RESTRICT (nombre: `fk_groups_company`)

---

#### `articles`
Catálogo de artículos de inventario del sistema legacy en `sigtools_beta`. Incluye campos de despacho y checklist añadidos durante el período auditado.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20)` | NO | — | PK, AUTO_INCREMENT |
| `sku` | `varchar(255)` | NO | — | UNIQUE |
| `name` | `text` | NO | — | — |
| `sub` | `text` | YES | NULL | — |
| `category` | `text` | NO | — | — |
| `group_id` | `bigint(20)` | YES | NULL | FK → `groups(id)` |
| `status` | `text` | NO | `'activo'` | — |
| `location` | `text` | YES | NULL | — |
| `acquisition_date` | `date` | YES | NULL | — |
| `image` | `text` | YES | NULL | — |
| `last_mod` | `timestamp` | NO | `current_timestamp()` | ON UPDATE `current_timestamp()` |
| `serial` | `text` | NO | — | — |
| `modified_by` | `text` | YES | NULL | — |
| `latest_note` | `text` | YES | NULL | — |
| `vendor` | `text` | YES | NULL | — |
| `quantity_send` | `int(11)` | YES | NULL | — |
| `tracking` | `text` | YES | NULL | — |
| `observations` | `text` | YES | NULL | — |
| `checklist_received` | `tinyint(1)` | YES | NULL | — |
| `checklist_notes` | `text` | YES | NULL | — |
| `checklist_date` | `datetime` | YES | NULL | — |

**FKs:** `group_id → groups(id)` RESTRICT/RESTRICT (nombre: `fk_articles_group`)

---

#### `activity_logs`
Registro de acciones realizadas sobre artículos de inventario.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20)` | NO | — | PK, AUTO_INCREMENT |
| `article_id` | `bigint(20)` | YES | NULL | FK → `articles(id)` |
| `action` | `text` | NO | — | — |
| `user_id` | `text` | YES | NULL | — |
| `timestamp` | `timestamp` | NO | `current_timestamp()` | — |
| `notes` | `text` | YES | NULL | — |

**FKs:** `article_id → articles(id)` RESTRICT/RESTRICT (nombre: `fk_activity_logs_article`)

---

#### `layers`
Capas de canvas en el módulo de instalaciones. Permite organizar dispositivos en planos independientes dentro de una instalación.

| Columna | Tipo | Nulo | Default |
|---------|------|------|---------|
| `id` | `bigint(20) unsigned` | NO | AUTO_INCREMENT |
| `name` | `varchar(255)` | NO | — |
| `created_at` | `timestamp` | YES | NULL |
| `updated_at` | `timestamp` | YES | NULL |

**PK:** `id`
**FKs entrantes:** `device_positions.layer_id`, `canvas_positions.layer_id`, `devices.layer_id`

---

#### `refresh_tokens`
Tokens de refresco para la autenticación de la plataforma web. Permite renovar sesiones sin re-autenticar con credenciales.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20) unsigned` | NO | — | PK, AUTO_INCREMENT |
| `user_id` | `bigint(20) unsigned` | NO | — | FK → `users(id)` |
| `token_hash` | `varchar(64)` | NO | — | UNIQUE (`uq_rt_token_hash`) |
| `expires_at` | `timestamp` | NO | `current_timestamp()` | — |
| `revoked` | `tinyint(1)` | NO | `0` | — |
| `revoked_at` | `timestamp` | YES | NULL | — |
| `created_at` | `timestamp` | NO | `current_timestamp()` | — |

**FKs:** `user_id → users(id)` RESTRICT/CASCADE (nombre: `fk_rt_user_id`)
**Índices:** `idx_rt_user_id` (non-unique, `user_id`)

---

#### `devices`
Dispositivos de red por sitio (Routers, PDUs, etc.). Tabla central del módulo de canvas; otras tablas referencian esta para posicionamiento y jerarquía.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20) unsigned` | NO | — | PK, AUTO_INCREMENT |
| `name` | `varchar(255)` | NO | — | — |
| `code` | `enum('Router','PDU','InterMapper','Other')` | NO | — | — |
| `device_type_id` | `bigint(20) unsigned` | YES | NULL | FK → `device_types(id)` |
| `address` | `varchar(255)` | NO | — | — |
| `notes` | `varchar(255)` | YES | NULL | — |
| `created_at` | `timestamp` | YES | NULL | — |
| `updated_at` | `timestamp` | YES | NULL | — |
| `intermapper_code` | `varchar(20)` | YES | `''` | — |
| `site_id` | `bigint(20) unsigned` | NO | — | FK → `sites(id)` |
| `layer_id` | `bigint(20) unsigned` | YES | NULL | FK → `layers(id)` |
| `status` | `int(11)` | YES | NULL | — |
| `deleted_at` | `timestamp` | YES | NULL | Soft-delete |
| `parent_id` | `bigint(20) unsigned` | YES | NULL | FK self-referencing → `devices(id)` |

**FKs:**
- `device_type_id → device_types(id)` CASCADE/SET NULL
- `layer_id → layers(id)` CASCADE/SET NULL
- `parent_id → devices(id)` CASCADE/SET NULL *(self-referencing)*
- `site_id → sites(id)` RESTRICT/RESTRICT

---

#### `device_positions`
Posición y rotación de un dispositivo `devices` en el canvas. La PK es el propio `device_id` (FK-as-PK: relación 1-a-1).

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `device_id` | `bigint(20) unsigned` | NO | — | PK (no AUTO_INCREMENT) |
| `layer_id` | `bigint(20) unsigned` | YES | NULL | FK → `layers(id)` |
| `x` | `double` | NO | `0` | — |
| `y` | `double` | NO | `0` | — |
| `rotation` | `double` | NO | `0` | — |
| `updated_at` | `timestamp` | NO | `current_timestamp()` | ON UPDATE |

**FKs:** `layer_id → layers(id)` CASCADE/SET NULL (nombre: `devpos_layer_fk`)

---

#### `installation_devices_link`
Tabla M2M que asocia dispositivos (`devices`) a instalaciones. Permite saber qué dispositivos participan en cada instalación.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20) unsigned` | NO | — | PK, AUTO_INCREMENT |
| `installation_id` | `bigint(20) unsigned` | NO | — | FK → `installations(id)` |
| `device_id` | `bigint(20) unsigned` | NO | — | FK → `devices(id)` |
| `created_at` | `timestamp` | YES | NULL | — |
| `deleted_at` | `timestamp` | YES | NULL | Soft-delete |

**UNIQUE:** `instdevlink_unique` (`installation_id, device_id`)
**FKs:**
- `installation_id → installations(id)` CASCADE/CASCADE (nombre: `instdevlink_installation_fk`)
- `device_id → devices(id)` CASCADE/CASCADE (nombre: `instdevlink_device_fk`)

---

#### `canvas_positions`
Posición y rotación en canvas para cualquier entidad: cámara, `other_device`, `device` o servidor. PK compuesta por `(entity_type, entity_id)` para identificar polimórficamente la entidad.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `entity_type` | `enum('camera','other_device','device','server')` | NO | — | PK (parte 1) |
| `entity_id` | `bigint(20) unsigned` | NO | — | PK (parte 2) |
| `installation_id` | `bigint(20) unsigned` | NO | — | FK → `installations(id)` |
| `layer_id` | `bigint(20) unsigned` | YES | NULL | FK → `layers(id)` |
| `x` | `double` | NO | `0` | — |
| `y` | `double` | NO | `0` | — |
| `rotation` | `double` | NO | `0` | — |
| `updated_at` | `timestamp` | NO | `current_timestamp()` | ON UPDATE |

**PK:** compuesto `(entity_type, entity_id)`
**FKs:**
- `installation_id → installations(id)` CASCADE/CASCADE (nombre: `canvaspos_installation_fk`)
- `layer_id → layers(id)` CASCADE/SET NULL (nombre: `canvaspos_layer_fk`)

**Índices:** `canvaspos_installation_idx` (`installation_id`), `canvaspos_layer_idx` (`layer_id`)

---

#### `device_hierarchy`
Árbol de dependencias entre dispositivos del canvas: quién alimenta (power), conecta (network) o soporta (mount) a quién. PK compuesta por los 5 campos para permitir múltiples tipos de vínculo entre el mismo par.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `parent_type` | `enum('camera','other_device','device')` | NO | — | PK (parte 1) |
| `parent_id` | `bigint(20) unsigned` | NO | — | PK (parte 2) |
| `child_type` | `enum('camera','other_device','device')` | NO | — | PK (parte 3) |
| `child_id` | `bigint(20) unsigned` | NO | — | PK (parte 4) |
| `link_type` | `enum('network','power','mount')` | NO | `'network'` | PK (parte 5) |
| `created_at` | `timestamp` | YES | NULL | — |

**PK:** compuesto `(parent_type, parent_id, child_type, child_id, link_type)`
**Índices:** `devhier_child_idx` (`child_type, child_id`)

---

#### `device_order`
Orden de visualización de entidades en el panel lateral de una instalación. Garantiza unicidad de posición (`order_num`) y de entidad dentro de la instalación.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20) unsigned` | NO | — | PK, AUTO_INCREMENT |
| `installation_id` | `bigint(20) unsigned` | NO | — | FK → `installations(id)` |
| `entity_type` | `enum('camera','other_device','device')` | NO | — | — |
| `entity_id` | `bigint(20) unsigned` | NO | — | — |
| `order_num` | `int(10) unsigned` | NO | — | — |
| `created_at` | `timestamp` | YES | NULL | — |
| `updated_at` | `timestamp` | YES | NULL | — |

**UNIQUE:** `devorder_entity_unique` (`installation_id, entity_type, entity_id`)
**UNIQUE:** `devorder_num_unique` (`installation_id, entity_type, order_num`)
**FK:** `installation_id → installations(id)` CASCADE/CASCADE (nombre: `devorder_installation_fk`)

---

#### `site_images`
Imágenes asociadas a un sitio: plano satelital o plano de piso. Base para el módulo de canvas georreferenciado.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20) unsigned` | NO | — | PK, AUTO_INCREMENT |
| `site_id` | `bigint(20) unsigned` | NO | — | FK → `sites(id)` |
| `image_type` | `enum('satellite','floor_plan')` | NO | — | — |
| `file_path` | `varchar(500)` | NO | — | — |
| `description` | `varchar(255)` | YES | NULL | — |
| `created_at` | `timestamp` | YES | NULL | — |
| `updated_at` | `timestamp` | YES | NULL | — |
| `deleted_at` | `timestamp` | YES | NULL | Soft-delete |

**FK:** `site_id → sites(id)` CASCADE/CASCADE (nombre: `siteimg_site_fk`)
**Índices:** `siteimg_site_idx` (`site_id`), `siteimg_type_idx` (`site_id, image_type`)

---

#### `project_sites`
Tabla de staging para sitios en proceso de onboarding. Un registro existe aquí antes de ser promovido y verificado en la tabla `sites`. Replica la estructura de `sites` más tres campos adicionales de logística de viaje y contrato.

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `bigint(20) unsigned` | NO | — | PK, AUTO_INCREMENT |
| `customer_group_id` | `bigint(20) unsigned` | NO | — | — |
| `it_backup_id` | `bigint(20) unsigned` | YES | NULL | — |
| `it_responsible_id` | `bigint(20) unsigned` | YES | NULL | — |
| `name` | `varchar(255)` | NO | — | — |
| `ip_address` | `varchar(250)` | YES | `'0.0.0.0'` | — |
| `state_code` | `varchar(2)` | YES | `'FL'` | — |
| `country_code` | `varchar(2)` | YES | `'US'` | — |
| `city` | `varchar(255)` | YES | NULL | — |
| `address` | `text` | YES | NULL | — |
| `dealership_info` | `text` | YES | NULL | — |
| `map_path` | `text` | YES | NULL | — |
| `lat` | `double(11,8)` | YES | NULL | — |
| `long` | `double(11,8)` | YES | NULL | — |
| `circuit_is_https` | `int(11)` | YES | `0` | — |
| `circuit_status` | `int(11)` | YES | `3` | — |
| `site_subdomain` | `varchar(255)` | YES | NULL | — |
| `site_subdomain_status` | `enum('none','ok','error')` | NO | `'none'` | — |
| `monitored` | `tinyint(1)` | NO | `1` | — |
| `maintenance` | `tinyint(1)` | NO | `1` | — |
| `rental` | `tinyint(1)` | NO | `1` | — |
| `installation_date` | `date` | YES | NULL | — |
| `site_status_id` | `bigint(20) unsigned` | YES | `1` | — |
| `site_id` | `bigint(20) unsigned` | YES | NULL | Referencia a `sites(id)` post-verificación |
| `cameras_count` | `int(11)` | NO | `0` | — |
| `preowned_cameras_count` | `int(11)` | NO | `0` | — |
| `exterior_cameras_count` | `int(11)` | NO | `0` | — |
| `teams_channelid` | `varchar(255)` | NO | `''` | — |
| `teams_teamid` | `varchar(255)` | NO | `''` | — |
| `timezone` | `varchar(50)` | YES | `'America/New_York'` | — |
| `verification_status` | `enum('pending','verified','rejected')` | NO | `'pending'` | — |
| `verified_by` | `bigint(20) unsigned` | YES | NULL | — |
| `verified_at` | `timestamp` | YES | NULL | — |
| `authorized_by` | `bigint(20) unsigned` | YES | NULL | — |
| `authorized_at` | `timestamp` | YES | NULL | — |
| `rejection_reason` | `text` | YES | NULL | — |
| `created_at` | `timestamp` | YES | NULL | — |
| `updated_at` | `timestamp` | YES | NULL | — |
| `deleted_at` | `timestamp` | YES | NULL | Soft-delete |
| `contract_value` | `decimal(14,2)` | YES | NULL | — |
| `hotel` | `text` | YES | NULL | — |
| `flight_details` | `text` | YES | NULL | — |

**Sin FK constraints declaradas** — las referencias a `customer_groups`, `users` y `sites` son lógicas (no enforced), igual que en la tabla `sites` original.

**Índices (12):**

| Nombre | Columna |
|--------|---------|
| `idx_ps_customer_group` | `customer_group_id` |
| `idx_ps_name` | `name` |
| `idx_ps_state_code` | `state_code` |
| `idx_ps_site_status` | `site_status_id` |
| `idx_ps_site_id` | `site_id` |
| `idx_ps_verification` | `verification_status` |
| `idx_ps_verified_by` | `verified_by` |
| `idx_ps_authorized_by` | `authorized_by` |
| `idx_ps_it_backup` | `it_backup_id` |
| `idx_ps_it_responsible` | `it_responsible_id` |
| `idx_ps_timezone` | `timezone` |
| `idx_ps_deleted_at` | `deleted_at` |

---

### 1.3 Sistema RBAC — Refactorización de PKs (2026-05-29)

> **Contexto:** Las tablas `app_roles`, `permissions`, `role_permissions` y `user_app_roles` existían antes del período auditado con PKs tipo `CHAR(36)` UUID. El 2026-05-29 fueron **dropeadas y recreadas** con PKs `INT UNSIGNED AUTO_INCREMENT` por razones de rendimiento (índices B-tree más eficientes con enteros, joins más rápidos, menor uso de espacio). Todos los datos fueron migrados usando el script `migrate_int_pks.py` incluido en el repositorio.

#### `app_roles`

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `int(10) unsigned` | NO | AUTO_INCREMENT | PK |
| `name` | `varchar(100)` | NO | — | UNIQUE (`uk_name`) |
| `label` | `varchar(100)` | NO | `''` | — |
| `description` | `text` | NO | — | — |
| `color` | `varchar(50)` | NO | `''` | — |
| `is_system` | `tinyint(1)` | NO | `0` | Protege el rol contra eliminación |
| `created_at` | `timestamp` | NO | `current_timestamp()` | — |

**Cambio vs. versión anterior:**
- PK era `CHAR(36)` UUID generado en aplicación → ahora `INT UNSIGNED` AUTO_INCREMENT generado por DB
- Se eliminó la columna `updated_at` (no existía en DB; era solo una declaración errónea en el modelo Django)
- Se añadieron las columnas `label` y `color` (existían en el schema real pero no en el modelo)

**Datos actuales (5 roles):**

| id | name | label | is_system |
|----|------|-------|:---------:|
| 1 | admin | Admin | 0 |
| 2 | designer | Designer | 0 |
| 3 | field_tech | Field Tech | 0 |
| 4 | inventory_op | Inventory Op | 0 |
| 5 | viewer | Viewer | 0 |

---

#### `permissions`

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `int(10) unsigned` | NO | AUTO_INCREMENT | PK |
| `key` | `varchar(100)` | NO | — | UNIQUE (`uk_key`) |
| `label` | `varchar(255)` | NO | `''` | — |
| `description` | `text` | NO | — | — |
| `app` | `varchar(50)` | NO | `''` | — |
| `category` | `varchar(50)` | NO | `''` | — |

**Cambio vs. versión anterior:** PK era `CHAR(36)` UUID → ahora `INT UNSIGNED` AUTO_INCREMENT.
**Datos actuales:** 44 registros (permisos granulares por app/categoría/acción).

---

#### `role_permissions`

| Columna | Tipo | Nulo | Restricciones |
|---------|------|------|---------------|
| `role_id` | `int(10) unsigned` | NO | PK (parte 1), FK → `app_roles(id)` |
| `permission_id` | `int(10) unsigned` | NO | PK (parte 2), FK → `permissions(id)` |

**PK:** compuesto `(role_id, permission_id)`

**FKs:**
- `role_id → app_roles(id)` ON DELETE CASCADE (nombre: `fk_rp_role`)
- `permission_id → permissions(id)` ON DELETE CASCADE (nombre: `fk_rp_perm`)

**Cambio vs. versión anterior:** FK columns eran `CHAR(36)`; ahora `INT UNSIGNED`. Se añadieron FK constraints explícitas con `ON DELETE CASCADE` (antes no existían constraints declaradas).

**Datos actuales:** 52 registros — admin: 44 permisos, field_tech: 8 permisos.

---

#### `user_app_roles`

| Columna | Tipo | Nulo | Default | Restricciones |
|---------|------|------|---------|---------------|
| `id` | `int(10) unsigned` | NO | AUTO_INCREMENT | PK |
| `user_id` | `bigint(20)` | NO | — | — |
| `role_id` | `int(10) unsigned` | NO | — | FK → `app_roles(id)` |
| `granted_at` | `timestamp` | NO | `current_timestamp()` | — |

**UNIQUE:** `uk_user_role` (`user_id, role_id`) — un usuario no puede tener el mismo rol dos veces.
**FK:** `role_id → app_roles(id)` ON DELETE CASCADE (nombre: `fk_uar_role`)

**Cambio vs. versión anterior:** `role_id` era `CHAR(36)` → ahora `INT UNSIGNED`.
**Datos actuales:** 4 registros.

---

### 1.4 Alteraciones a tablas existentes

#### `cameras` — columnas y constraints añadidos (2026-05-26)

| Elemento | Detalle |
|----------|---------|
| Nueva columna | `device_id bigint(20) unsigned NULL` |
| Nueva columna | `canvas_instance_id varchar(255) NULL` |
| Nuevo índice | `uq_cam_instance` UNIQUE (`installation_id, canvas_instance_id`) |
| Nueva FK | `cameras_device_id_foreign`: `device_id → devices(id)` CASCADE/CASCADE |

**Propósito:** Vincular cada cámara con un nodo en la tabla `devices` para posicionamiento en canvas, y registrar el identificador de instancia dentro del canvas de la instalación.

---

#### `other_devices` — columnas y constraints añadidos (2026-05-26)

| Elemento | Detalle |
|----------|---------|
| Nueva columna | `device_id bigint(20) unsigned NULL` |
| Nueva columna | `canvas_instance_id varchar(255) NULL` |
| Nuevo índice | `uq_od_instance` UNIQUE (`installation_id, canvas_instance_id`) |
| Nueva FK | `other_devices_device_id_foreign`: `device_id → devices(id)` CASCADE/CASCADE |

**Propósito:** Mismo que en `cameras` — integración con el módulo de canvas de instalaciones.

---

### 1.5 Diagramas de relaciones

#### RBAC

```
users
  id BIGINT PK
  │
  └──< user_app_roles
         id        INT UNSIGNED PK
         user_id   BIGINT  ──── (ref lógica, sin FK declarada)
         role_id   INT ─────────────────────────────┐
         granted_at TIMESTAMP                        │ fk_uar_role
                                                     │ ON DELETE CASCADE
                                                     ▼
                                               app_roles
                                                 id        INT PK
                                                 name      VARCHAR UNIQUE
                                                 label, description, color
                                                 is_system TINYINT
                                                 created_at TIMESTAMP
                                                     │
                                    ┌────────────────┘
                                    │ fk_rp_role
                                    ▼
                               role_permissions
                                 role_id       INT ──── fk_rp_role CASCADE
                                 permission_id INT ──── fk_rp_perm CASCADE
                                                             │
                                                             ▼
                                                       permissions
                                                         id       INT PK
                                                         key      VARCHAR UNIQUE
                                                         label, description
                                                         app, category
```

#### Canvas e instalaciones

```
sites ──< installations
              │
              ├──< canvas_positions (entity_type + entity_id)  ──── layer_id → layers
              │
              ├──< device_order (installation_id)
              │
              └──< installation_devices_link
                         device_id ──────────────────────────> devices
                                                                    ├── device_type_id → device_types
                                                                    ├── layer_id       → layers
                                                                    ├── parent_id      → devices (self)
                                                                    └── site_id        → sites

cameras       ── device_id ────> devices
other_devices ── device_id ────> devices

device_positions ── device_id (PK=FK, 1-a-1 con devices)
                 └── layer_id → layers

device_hierarchy: parent(type+id) ──── child(type+id)
                  link_type: network | power | mount

sites ──< site_images (satellite | floor_plan)
```

#### Inventario legacy

```
companies
    │
    └──< groups
              │
              └──< articles
                       │
                       └──< activity_logs
```

---

## SECCIÓN 2 — Guía de Transición a Producción

### 2.1 Prerequisitos

Antes de ejecutar cualquier DDL, verificar que las siguientes tablas ya existen en `sigtools_beta` de producción (son tablas preexistentes que sirven de referencia):

```sql
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'sigtools_beta'
  AND TABLE_NAME IN (
    'users', 'sites', 'installations', 'cameras',
    'other_devices', 'device_types', 'camera_models', 'areas'
  );
-- Deben aparecer las 8 tablas
```

---

### 2.2 Orden de ejecución recomendado

```
Paso 1  — companies
Paso 2  — groups            (depende de companies)
Paso 3  — articles          (depende de groups)
Paso 4  — activity_logs     (depende de articles)
Paso 5  — refresh_tokens    (depende de users — preexistente)
Paso 6  — layers
Paso 7  — devices           (depende de sites, device_types, layers — preexistentes)
Paso 8  — device_positions  (depende de layers)
Paso 9  — installation_devices_link  (depende de installations, devices)
Paso 10 — canvas_positions  (depende de installations, layers)
Paso 11 — device_hierarchy
Paso 12 — device_order      (depende de installations)
Paso 13 — site_images       (depende de sites)
Paso 14 — ALTER cameras     (depende de devices)
Paso 15 — ALTER other_devices (depende de devices)
Paso 16 — project_sites
Paso 17 — app_roles
Paso 18 — permissions
Paso 19 — role_permissions  (depende de app_roles, permissions)
Paso 20 — user_app_roles    (depende de app_roles)
Paso 21 — Seed: roles y permisos base
```

---

### 2.3 Scripts DDL

#### Paso 1–4 — Inventario legacy

```sql
-- 1. companies
CREATE TABLE IF NOT EXISTS companies (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    logo_url    TEXT,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. groups
CREATE TABLE IF NOT EXISTS `groups` (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    icon_name   TEXT,
    color       TEXT,
    company_id  BIGINT,
    PRIMARY KEY (id),
    CONSTRAINT fk_groups_company
        FOREIGN KEY (company_id) REFERENCES companies(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. articles
CREATE TABLE IF NOT EXISTS articles (
    id                 BIGINT       NOT NULL AUTO_INCREMENT,
    sku                VARCHAR(255) NOT NULL,
    name               TEXT         NOT NULL,
    sub                TEXT,
    category           TEXT         NOT NULL,
    group_id           BIGINT,
    status             TEXT         NOT NULL DEFAULT 'activo',
    location           TEXT,
    acquisition_date   DATE,
    image              TEXT,
    last_mod           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    serial             TEXT         NOT NULL,
    modified_by        TEXT,
    latest_note        TEXT,
    vendor             TEXT,
    quantity_send      INT,
    tracking           TEXT,
    observations       TEXT,
    checklist_received TINYINT(1),
    checklist_notes    TEXT,
    checklist_date     DATETIME,
    PRIMARY KEY (id),
    UNIQUE KEY (sku),
    CONSTRAINT fk_articles_group
        FOREIGN KEY (group_id) REFERENCES `groups`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. activity_logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id         BIGINT    NOT NULL AUTO_INCREMENT,
    article_id BIGINT,
    action     TEXT      NOT NULL,
    user_id    TEXT,
    timestamp  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes      TEXT,
    PRIMARY KEY (id),
    KEY fk_activity_logs_article (article_id),
    CONSTRAINT fk_activity_logs_article
        FOREIGN KEY (article_id) REFERENCES articles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Paso 5 — Autenticación

```sql
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    BIGINT UNSIGNED NOT NULL,
    token_hash VARCHAR(64)     NOT NULL,
    expires_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked    TINYINT(1)      NOT NULL DEFAULT 0,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_rt_token_hash (token_hash),
    KEY idx_rt_user_id (user_id),
    CONSTRAINT fk_rt_user_id
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Paso 6–13 — Canvas e instalaciones

```sql
-- 6. layers
CREATE TABLE IF NOT EXISTS layers (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name       VARCHAR(255)    NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. devices  (verificar primero si ya existe — ver nota en riesgos)
CREATE TABLE IF NOT EXISTS devices (
    id               BIGINT UNSIGNED                          NOT NULL AUTO_INCREMENT,
    name             VARCHAR(255)                             NOT NULL,
    code             ENUM('Router','PDU','InterMapper','Other') NOT NULL,
    device_type_id   BIGINT UNSIGNED,
    address          VARCHAR(255)                             NOT NULL,
    notes            VARCHAR(255),
    created_at       TIMESTAMP,
    updated_at       TIMESTAMP,
    intermapper_code VARCHAR(20)                                       DEFAULT '',
    site_id          BIGINT UNSIGNED                          NOT NULL,
    layer_id         BIGINT UNSIGNED,
    status           INT,
    deleted_at       TIMESTAMP,
    parent_id        BIGINT UNSIGNED,
    PRIMARY KEY (id),
    CONSTRAINT devices_device_type_id_foreign
        FOREIGN KEY (device_type_id) REFERENCES device_types(id)
        ON DELETE SET NULL,
    CONSTRAINT devices_layer_id_foreign
        FOREIGN KEY (layer_id) REFERENCES layers(id)
        ON DELETE SET NULL,
    CONSTRAINT devices_parent_id_foreign
        FOREIGN KEY (parent_id) REFERENCES devices(id)
        ON DELETE SET NULL,
    CONSTRAINT devices_site_id_foreign
        FOREIGN KEY (site_id) REFERENCES sites(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. device_positions
CREATE TABLE IF NOT EXISTS device_positions (
    device_id  BIGINT UNSIGNED NOT NULL,
    layer_id   BIGINT UNSIGNED,
    x          DOUBLE NOT NULL DEFAULT 0,
    y          DOUBLE NOT NULL DEFAULT 0,
    rotation   DOUBLE NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (device_id),
    KEY devpos_layer_idx (layer_id),
    CONSTRAINT devpos_layer_fk
        FOREIGN KEY (layer_id) REFERENCES layers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. installation_devices_link
CREATE TABLE IF NOT EXISTS installation_devices_link (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    installation_id BIGINT UNSIGNED NOT NULL,
    device_id       BIGINT UNSIGNED NOT NULL,
    created_at      TIMESTAMP,
    deleted_at      TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY instdevlink_unique (installation_id, device_id),
    KEY instdevlink_installation_idx (installation_id),
    KEY instdevlink_device_idx (device_id),
    CONSTRAINT instdevlink_installation_fk
        FOREIGN KEY (installation_id) REFERENCES installations(id) ON DELETE CASCADE,
    CONSTRAINT instdevlink_device_fk
        FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10. canvas_positions
CREATE TABLE IF NOT EXISTS canvas_positions (
    entity_type     ENUM('camera','other_device','device','server') NOT NULL,
    entity_id       BIGINT UNSIGNED NOT NULL,
    installation_id BIGINT UNSIGNED NOT NULL,
    layer_id        BIGINT UNSIGNED,
    x               DOUBLE NOT NULL DEFAULT 0,
    y               DOUBLE NOT NULL DEFAULT 0,
    rotation        DOUBLE NOT NULL DEFAULT 0,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_type, entity_id),
    KEY canvaspos_installation_idx (installation_id),
    KEY canvaspos_layer_idx (layer_id),
    CONSTRAINT canvaspos_installation_fk
        FOREIGN KEY (installation_id) REFERENCES installations(id) ON DELETE CASCADE,
    CONSTRAINT canvaspos_layer_fk
        FOREIGN KEY (layer_id) REFERENCES layers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11. device_hierarchy
CREATE TABLE IF NOT EXISTS device_hierarchy (
    parent_type ENUM('camera','other_device','device') NOT NULL,
    parent_id   BIGINT UNSIGNED                        NOT NULL,
    child_type  ENUM('camera','other_device','device') NOT NULL,
    child_id    BIGINT UNSIGNED                        NOT NULL,
    link_type   ENUM('network','power','mount')        NOT NULL DEFAULT 'network',
    created_at  TIMESTAMP,
    PRIMARY KEY (parent_type, parent_id, child_type, child_id, link_type),
    KEY devhier_child_idx (child_type, child_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 12. device_order
CREATE TABLE IF NOT EXISTS device_order (
    id              BIGINT UNSIGNED                        NOT NULL AUTO_INCREMENT,
    installation_id BIGINT UNSIGNED                        NOT NULL,
    entity_type     ENUM('camera','other_device','device') NOT NULL,
    entity_id       BIGINT UNSIGNED                        NOT NULL,
    order_num       INT UNSIGNED                           NOT NULL,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY devorder_entity_unique (installation_id, entity_type, entity_id),
    UNIQUE KEY devorder_num_unique    (installation_id, entity_type, order_num),
    KEY devorder_installation_idx (installation_id),
    CONSTRAINT devorder_installation_fk
        FOREIGN KEY (installation_id) REFERENCES installations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 13. site_images
CREATE TABLE IF NOT EXISTS site_images (
    id          BIGINT UNSIGNED              NOT NULL AUTO_INCREMENT,
    site_id     BIGINT UNSIGNED              NOT NULL,
    image_type  ENUM('satellite','floor_plan') NOT NULL,
    file_path   VARCHAR(500)                 NOT NULL,
    description VARCHAR(255),
    created_at  TIMESTAMP,
    updated_at  TIMESTAMP,
    deleted_at  TIMESTAMP,
    PRIMARY KEY (id),
    KEY siteimg_site_idx  (site_id),
    KEY siteimg_type_idx  (site_id, image_type),
    CONSTRAINT siteimg_site_fk
        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Pasos 14–15 — ALTER sobre tablas existentes

> ⚠️ Si las tablas tienen datos en producción, usar `ALTER TABLE`. Si `ADD COLUMN IF NOT EXISTS` no está disponible (MySQL < 8.0), verificar primero con `SHOW COLUMNS`.

```sql
-- 14. cameras
ALTER TABLE cameras
    ADD COLUMN device_id          BIGINT UNSIGNED NULL,
    ADD COLUMN canvas_instance_id VARCHAR(255)    NULL;

ALTER TABLE cameras
    ADD CONSTRAINT cameras_device_id_foreign
        FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    ADD UNIQUE KEY uq_cam_instance (installation_id, canvas_instance_id);

-- 15. other_devices
ALTER TABLE other_devices
    ADD COLUMN device_id          BIGINT UNSIGNED NULL,
    ADD COLUMN canvas_instance_id VARCHAR(255)    NULL;

ALTER TABLE other_devices
    ADD CONSTRAINT other_devices_device_id_foreign
        FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
    ADD UNIQUE KEY uq_od_instance (installation_id, canvas_instance_id);
```

#### Paso 16 — project_sites

```sql
CREATE TABLE IF NOT EXISTS project_sites (
    id                     BIGINT UNSIGNED                          NOT NULL AUTO_INCREMENT,
    customer_group_id      BIGINT UNSIGNED                          NOT NULL,
    it_backup_id           BIGINT UNSIGNED,
    it_responsible_id      BIGINT UNSIGNED,
    name                   VARCHAR(255)                             NOT NULL,
    ip_address             VARCHAR(250)                                      DEFAULT '0.0.0.0',
    state_code             VARCHAR(2)                                        DEFAULT 'FL',
    country_code           VARCHAR(2)                                        DEFAULT 'US',
    city                   VARCHAR(255),
    address                TEXT,
    dealership_info        TEXT,
    map_path               TEXT,
    lat                    DOUBLE(11,8),
    `long`                 DOUBLE(11,8),
    circuit_is_https       INT                                               DEFAULT 0,
    circuit_status         INT                                               DEFAULT 3,
    site_subdomain         VARCHAR(255),
    site_subdomain_status  ENUM('none','ok','error')                NOT NULL DEFAULT 'none',
    monitored              TINYINT(1)                               NOT NULL DEFAULT 1,
    maintenance            TINYINT(1)                               NOT NULL DEFAULT 1,
    rental                 TINYINT(1)                               NOT NULL DEFAULT 1,
    installation_date      DATE,
    site_status_id         BIGINT UNSIGNED                                   DEFAULT 1,
    site_id                BIGINT UNSIGNED,
    cameras_count          INT                                      NOT NULL DEFAULT 0,
    preowned_cameras_count INT                                      NOT NULL DEFAULT 0,
    exterior_cameras_count INT                                      NOT NULL DEFAULT 0,
    teams_channelid        VARCHAR(255)                             NOT NULL DEFAULT '',
    teams_teamid           VARCHAR(255)                             NOT NULL DEFAULT '',
    timezone               VARCHAR(50)                                       DEFAULT 'America/New_York',
    verification_status    ENUM('pending','verified','rejected')    NOT NULL DEFAULT 'pending',
    verified_by            BIGINT UNSIGNED,
    verified_at            TIMESTAMP,
    authorized_by          BIGINT UNSIGNED,
    authorized_at          TIMESTAMP,
    rejection_reason       TEXT,
    created_at             TIMESTAMP,
    updated_at             TIMESTAMP,
    deleted_at             TIMESTAMP,
    contract_value         DECIMAL(14,2),
    hotel                  TEXT,
    flight_details         TEXT,
    PRIMARY KEY (id),
    KEY idx_ps_customer_group  (customer_group_id),
    KEY idx_ps_name            (name),
    KEY idx_ps_state_code      (state_code),
    KEY idx_ps_site_status     (site_status_id),
    KEY idx_ps_site_id         (site_id),
    KEY idx_ps_verification    (verification_status),
    KEY idx_ps_verified_by     (verified_by),
    KEY idx_ps_authorized_by   (authorized_by),
    KEY idx_ps_it_backup       (it_backup_id),
    KEY idx_ps_it_responsible  (it_responsible_id),
    KEY idx_ps_timezone        (timezone),
    KEY idx_ps_deleted_at      (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Pasos 17–20 — RBAC

**Opción A — Producción no tiene estas tablas (instalación fresca):**

```sql
-- 17. app_roles
CREATE TABLE IF NOT EXISTS app_roles (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(100) NOT NULL,
    label       VARCHAR(100) NOT NULL DEFAULT '',
    description TEXT         NOT NULL,
    color       VARCHAR(50)  NOT NULL DEFAULT '',
    is_system   TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 18. permissions
CREATE TABLE IF NOT EXISTS permissions (
    id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `key`       VARCHAR(100)  NOT NULL,
    label       VARCHAR(255)  NOT NULL DEFAULT '',
    description TEXT          NOT NULL,
    app         VARCHAR(50)   NOT NULL DEFAULT '',
    category    VARCHAR(50)   NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    UNIQUE KEY uk_key (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 19. role_permissions
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INT UNSIGNED NOT NULL,
    permission_id INT UNSIGNED NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_rp_role FOREIGN KEY (role_id)
        REFERENCES app_roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id)
        REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 20. user_app_roles
CREATE TABLE IF NOT EXISTS user_app_roles (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    BIGINT       NOT NULL,
    role_id    INT UNSIGNED NOT NULL,
    granted_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_role (user_id, role_id),
    CONSTRAINT fk_uar_role FOREIGN KEY (role_id)
        REFERENCES app_roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Opción B — Producción ya tiene estas tablas con PKs UUID:**

```bash
# El script lee datos actuales → reconstruye tablas → reinserta con IDs INT deterministas
python manage.py shell < migrate_int_pks.py
```

#### Paso 21 — Seed de permisos y roles base

```bash
python manage.py shell < insert_perms.py
```

---

### 2.4 Validaciones post-migración

```sql
-- 1. Todas las tablas nuevas presentes
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'sigtools_beta'
  AND TABLE_NAME IN (
    'activity_logs','companies','articles','groups','layers',
    'refresh_tokens','devices','device_positions',
    'installation_devices_link','canvas_positions',
    'device_hierarchy','device_order','site_images',
    'project_sites','app_roles','permissions',
    'role_permissions','user_app_roles'
  )
ORDER BY TABLE_NAME;
-- Esperado: 18 filas

-- 2. PKs INT en tablas RBAC
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'sigtools_beta'
  AND TABLE_NAME IN ('app_roles','permissions','user_app_roles')
  AND COLUMN_KEY = 'PRI';
-- Esperado: los 3 PKs con tipo int(10) unsigned

-- 3. FK constraints RBAC con CASCADE
SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE
FROM information_schema.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'sigtools_beta'
  AND CONSTRAINT_NAME IN ('fk_rp_role','fk_rp_perm','fk_uar_role');
-- Esperado: 3 filas, DELETE_RULE = 'CASCADE'

-- 4. Columnas nuevas en cameras y other_devices
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'sigtools_beta'
  AND TABLE_NAME IN ('cameras','other_devices')
  AND COLUMN_NAME IN ('device_id','canvas_instance_id');
-- Esperado: 4 filas

-- 5. Conteo de datos RBAC
SELECT
    (SELECT COUNT(*) FROM app_roles)      AS roles,
    (SELECT COUNT(*) FROM permissions)    AS permisos,
    (SELECT COUNT(*) FROM role_permissions) AS asignaciones_rol,
    (SELECT COUNT(*) FROM user_app_roles) AS usuarios_asignados;
-- Esperado: 5, 44, 52, 4

-- 6. Integridad FK — no deben quedar huérfanos
SELECT COUNT(*) FROM role_permissions rp
LEFT JOIN app_roles ar ON ar.id = rp.role_id
WHERE ar.id IS NULL;
-- Esperado: 0

SELECT COUNT(*) FROM user_app_roles uar
LEFT JOIN app_roles ar ON ar.id = uar.role_id
WHERE ar.id IS NULL;
-- Esperado: 0

-- 7. Check Django
-- Ejecutar desde el servidor: python manage.py check
-- Esperado: "System check identified no issues (0 silenced)."
```

---

### 2.5 Riesgos y mitigaciones

| # | Riesgo | Impacto | Mitigación |
|---|--------|---------|------------|
| 1 | Producción tiene tablas RBAC con UUID PKs | Alto — IDs distintos, todas las asignaciones de usuarios quedarían inválidas | Usar `migrate_int_pks.py`; hacer **backup previo** de las 4 tablas; ejecutar en ventana de mantenimiento con sesiones suspendidas |
| 2 | `cameras`/`other_devices` con millones de filas | Medio — `ALTER TABLE` con lock en tabla grande puede tardar minutos | Evaluar `pt-online-schema-change` o `gh-ost` para ALTER sin downtime; ejecutar en horario de baja actividad |
| 3 | `devices` ya existe en producción con esquema distinto | Medio — el `CREATE TABLE IF NOT EXISTS` no fallará pero no añadirá columnas nuevas | Verificar con `SHOW CREATE TABLE devices` en producción; agregar columnas faltantes con `ALTER TABLE IF NOT EXISTS` |
| 4 | `unique` en `canvas_instance_id` con valores NULL existentes | Bajo | MySQL/MariaDB permite múltiples NULL en índice UNIQUE — no bloquea filas sin `canvas_instance_id` |
| 5 | El script `migrate_int_pks.py` no preserva UUIDs originales | Alto si hay sistemas externos que usen esos UUIDs | Confirmar que ningún sistema externo referencia los UUIDs antes de ejecutar |
| 6 | FK `refresh_tokens.user_id ON DELETE CASCADE` | Bajo | Si se elimina un usuario, sus tokens se eliminan automáticamente — comportamiento correcto y esperado |

---

### 2.6 Rollback

#### Rollback completo — tablas nuevas sigtools_beta

```sql
SET FOREIGN_KEY_CHECKS = 0;

-- RBAC
DROP TABLE IF EXISTS user_app_roles;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS app_roles;

-- Staging
DROP TABLE IF EXISTS project_sites;

-- Canvas
DROP TABLE IF EXISTS site_images;
DROP TABLE IF EXISTS device_order;
DROP TABLE IF EXISTS device_hierarchy;
DROP TABLE IF EXISTS canvas_positions;
DROP TABLE IF EXISTS installation_devices_link;
DROP TABLE IF EXISTS device_positions;
DROP TABLE IF EXISTS devices;
DROP TABLE IF EXISTS layers;

-- Auth
DROP TABLE IF EXISTS refresh_tokens;

-- Inventario legacy
DROP TABLE IF EXISTS activity_logs;
DROP TABLE IF EXISTS articles;
DROP TABLE IF EXISTS `groups`;
DROP TABLE IF EXISTS companies;

SET FOREIGN_KEY_CHECKS = 1;
```

#### Rollback de ALTERs sobre tablas existentes

```sql
-- cameras
ALTER TABLE cameras
    DROP FOREIGN KEY cameras_device_id_foreign,
    DROP INDEX uq_cam_instance,
    DROP COLUMN device_id,
    DROP COLUMN canvas_instance_id;

-- other_devices
ALTER TABLE other_devices
    DROP FOREIGN KEY other_devices_device_id_foreign,
    DROP INDEX uq_od_instance,
    DROP COLUMN device_id,
    DROP COLUMN canvas_instance_id;
```

#### Rollback RBAC a UUID (si aplica)

El script `migrate_int_pks.py` no guarda los UUIDs originales. Si producción usaba UUIDs y se ejecutó el script, el único rollback disponible es **restaurar desde backup**. Por esta razón es obligatorio hacer backup de las 4 tablas antes de ejecutar el script en producción.

---

*Documento generado consultando `information_schema` en tiempo real contra el ambiente de desarrollo. Refleja el estado exacto de `sigtools_beta` al 2026-05-31.*
