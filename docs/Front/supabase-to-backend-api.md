# SIG Installations — Supabase → Backend API Migration Guide

Documento de referencia exhaustivo para replicar en el backend Django todos los datos que el frontend actualmente solicita a Supabase. Para cada operación se especifica: qué tablas/buckets se consultan, qué datos se envían, qué estructura exacta se recibe, y el endpoint REST equivalente que el backend debe exponer.

---

## Índice

1. [Modelo de datos — tablas involucradas](#1-modelo-de-datos--tablas-involucradas)
2. [Proyectos (`sig_projects`)](#2-proyectos-sig_projects)
   - [GET /projects — listar](#21-get-projects--listar-todos)
   - [GET /projects/:id — detalle](#22-get-projectsid--detalle)
   - [POST /projects — crear](#23-post-projects--crear)
   - [PATCH /projects/:id — actualizar con concurrencia optimista](#24-patch-projectsid--actualizar)
   - [DELETE /projects/:id — eliminar](#25-delete-projectsid--eliminar)
   - [PATCH /projects/:id/name — renombrar](#26-patch-projectsidname--renombrar)
3. [Realtime — actualizaciones en vivo](#3-realtime--actualizaciones-en-vivo)
4. [Storage — fotos de Site Surveys](#4-storage--fotos-de-site-surveys)
   - [POST /storage/survey-photos — subir foto](#41-post-storagesurvey-photos--subir-foto)
   - [DELETE /storage/survey-photos — eliminar foto](#42-delete-storagesurvey-photos--eliminar-foto)
5. [Admin — Usuarios (`profiles` + `user_roles`)](#5-admin--usuarios)
   - [GET /admin/users — listar usuarios](#51-get-adminusers--listar-usuarios)
   - [POST /admin/users — crear usuario](#52-post-adminusers--crear-usuario)
   - [PATCH /admin/users/:id — actualizar usuario](#53-patch-adminusersid--actualizar-usuario)
   - [DELETE /admin/users/:id — desactivar usuario](#54-delete-adminusersid--desactivar-usuario)
6. [Admin — Roles (`roles` + `role_permissions`)](#6-admin--roles)
   - [GET /admin/roles — listar roles](#61-get-adminroles--listar-roles)
   - [POST /admin/roles — crear rol](#62-post-adminroles--crear-rol)
   - [PATCH /admin/roles/:id — actualizar rol](#63-patch-adminrolesid--actualizar-rol)
   - [DELETE /admin/roles/:id — eliminar rol](#64-delete-adminrolesid--eliminar-rol)
7. [Admin — Permisos (`permissions`)](#7-admin--permisos)
   - [GET /admin/permissions — listar permisos](#71-get-adminpermissions--listar-permisos)
8. [Resumen de endpoints](#8-resumen-de-endpoints)
9. [Notas de implementación](#9-notas-de-implementación)

---

## 1. Modelo de datos — tablas involucradas

El frontend actualmente consulta las siguientes tablas y buckets de Supabase:

| Recurso | Tipo | Descripción |
|---|---|---|
| `sig_projects` | Tabla PostgreSQL | Proyectos de instalación (datos completos en columna JSONB `data`) |
| `profiles` | Tabla PostgreSQL | Perfil de usuario (linked to auth.users) |
| `roles` | Tabla PostgreSQL | Roles del sistema (admin, viewer, etc.) |
| `permissions` | Tabla PostgreSQL | Permisos atómicos por feature |
| `user_roles` | Tabla PostgreSQL | Tabla pivote usuario ↔ rol |
| `role_permissions` | Tabla PostgreSQL | Tabla pivote rol ↔ permiso |
| `site-survey-photos` | Storage Bucket | Fotos georeferenciadas del campo |

---

## 2. Proyectos (`sig_projects`)

### 2.1 `GET /projects` — listar todos

**Supabase query:**
```typescript
supabase
  .from('sig_projects')
  .select('id, name, updated_at, version, data')
  .order('updated_at', { ascending: false })
```

**SQL equivalente:**
```sql
SELECT id, name, updated_at, version, data
FROM sig_projects
ORDER BY updated_at DESC;
```

**Request del frontend:**
```http
GET /api/v1/installations/projects/
```
Sin body. Requiere cookie `sig_token`.

**Response esperado `200 OK`:**
```json
[
  {
    "id": "proj-abc123",
    "name": "Sede Norte",
    "updated_at": "2026-05-10T14:30:00.000Z",
    "version": 5,
    "data": {
      "type": "tactical",
      "schemaVersion": 1,
      "devices": [],
      "enlaces": [],
      "drawings": [],
      "sitios": [],
      "siteSurveys": []
    }
  }
]
```

**Response `200 OK` — lista vacía:**
```json
[]
```

**Estructura del objeto `Project`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` (UUID o libre) | Identificador único. El frontend genera un UUID v4 propio antes de crear |
| `name` | `string` | Nombre del proyecto |
| `updated_at` | `string` ISO 8601 | Última modificación |
| `version` | `integer` | Token de concurrencia optimista. Empieza en `1`, se incrementa en cada update |
| `data` | `object` (JSONB) | Payload completo del proyecto — ver estructura abajo |

**Estructura de `data` (ProjectData):**

| Campo | Tipo | Descripción |
|---|---|---|
| `type` | `"tactical" \| "survey"` | Tipo de proyecto |
| `schemaVersion` | `integer` | Siempre `1` en la versión actual |
| `devices` | `DeviceInstance[]` | Dispositivos en el mapa |
| `enlaces` | `Enlace[]` | Conexiones entre dispositivos |
| `drawings` | `DrawingItem[]` | Polígonos/líneas/círculos dibujados |
| `sitios` | `Sitio[]` | Sitios (cada proyecto puede tener múltiples sitios con coordenadas) |
| `siteSurveys` | `SiteSurveyMarker[]` | Marcadores de foto del campo |

> **Importante**: El campo `data` debe almacenarse y devolverse como un objeto JSON opaco. El backend no necesita parsear su contenido, solo guardarlo y devolverlo íntegro.

---

### 2.2 `GET /projects/:id` — detalle

**Supabase query:**
```typescript
supabase
  .from('sig_projects')
  .select('*')
  .eq('id', id)
  .maybeSingle()
```

**SQL equivalente:**
```sql
SELECT * FROM sig_projects WHERE id = $1 LIMIT 1;
```

**Request del frontend:**
```http
GET /api/v1/installations/projects/{id}/
```

**Response `200 OK`:**
```json
{
  "id": "proj-abc123",
  "name": "Sede Norte",
  "updated_at": "2026-05-10T14:30:00.000Z",
  "version": 5,
  "data": { ... }
}
```

**Response `404 Not Found`:**
```json
{
  "detail": "Not found."
}
```

> `.maybeSingle()` en Supabase devuelve `null` si no existe (no lanza error). El backend debe responder `404`.

---

### 2.3 `POST /projects` — crear

**Supabase query:**
```typescript
supabase
  .from('sig_projects')
  .insert({
    id,          // generado por el frontend
    name,
    data: { ...data, schemaVersion: 1 },
    version: 1,
    updated_at: new Date().toISOString(),
  })
  .select()
  .single()
```

**Request del frontend:**
```http
POST /api/v1/installations/projects/
Content-Type: application/json

{
  "id": "proj-abc123",
  "name": "Sede Norte",
  "data": {
    "type": "tactical",
    "schemaVersion": 1,
    "devices": [],
    "enlaces": [],
    "drawings": [],
    "sitios": [
      {
        "id": "sitio-xyz",
        "nombre": "Initial Site",
        "lat": 19.4326,
        "lng": -99.1332,
        "zoom": 18
      }
    ],
    "siteSurveys": []
  }
}
```

> **Nota**: El frontend siempre incluye `id` en el body. El backend debe respetar ese ID (no generar uno propio). `version` y `updated_at` los fija el backend.

**Response `201 Created`:**
```json
{
  "id": "proj-abc123",
  "name": "Sede Norte",
  "updated_at": "2026-05-10T14:30:00.000Z",
  "version": 1,
  "data": {
    "type": "tactical",
    "schemaVersion": 1,
    "devices": [],
    "enlaces": [],
    "drawings": [],
    "sitios": [...],
    "siteSurveys": []
  }
}
```

**Response `409 Conflict`** (ID ya existe):
```json
{
  "detail": "A project with this ID already exists."
}
```

> Supabase devuelve código `23505` (unique violation) cuando el ID ya existe. El frontend lo detecta y hace un update en su lugar. El backend debe responder `409`.

---

### 2.4 `PATCH /projects/:id` — actualizar

Esta es la operación más crítica. Usa **concurrencia optimista**: el frontend envía la versión que espera encontrar. Si la versión en la base de datos ya no coincide (otro usuario guardó antes), el backend debe rechazar el update con `409`.

**Supabase query:**
```typescript
supabase
  .from('sig_projects')
  .update({
    name,
    data: { ...data, schemaVersion: 1 },
    version: expectedVersion + 1,    // incrementa la versión
    updated_at: new Date().toISOString(),
  })
  .eq('id', id)
  .eq('version', expectedVersion)    // ← condición de concurrencia
  .select()
  .maybeSingle()
```

**SQL equivalente:**
```sql
UPDATE sig_projects
SET
  name       = $1,
  data       = $2,
  version    = $3 + 1,
  updated_at = NOW()
WHERE id      = $4
  AND version = $3          -- si no coincide, la query devuelve 0 filas
RETURNING *;
```

Si la query devuelve **0 filas** (version mismatch o row eliminado), el frontend hace un `GET /projects/:id` para obtener la versión más reciente y lanza `ConflictError`.

**Request del frontend:**
```http
PATCH /api/v1/installations/projects/{id}/
Content-Type: application/json

{
  "name": "Sede Norte - Actualizado",
  "expected_version": 5,
  "data": {
    "type": "tactical",
    "schemaVersion": 1,
    "devices": [...],
    "enlaces": [...],
    "drawings": [...],
    "sitios": [...],
    "siteSurveys": [...]
  }
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `name` | `string` | Nuevo nombre |
| `expected_version` | `integer` | Versión que el cliente tiene actualmente. El backend actualiza solo si `version == expected_version` |
| `data` | `object` | Datos completos del proyecto |

**Response `200 OK`** (update exitoso):
```json
{
  "id": "proj-abc123",
  "name": "Sede Norte - Actualizado",
  "updated_at": "2026-05-10T15:00:00.000Z",
  "version": 6,
  "data": { ... }
}
```

**Response `409 Conflict`** (version mismatch):
```json
{
  "detail": "Conflict: the project was modified by another user.",
  "latest": {
    "id": "proj-abc123",
    "name": "Sede Norte - Otro usuario",
    "updated_at": "2026-05-10T14:55:00.000Z",
    "version": 6,
    "data": { ... }
  }
}
```

> El campo `latest` en el `409` es lo que el frontend usa para reconciliar. Debe incluir el objeto completo con `version` actualizada.

**Response `404 Not Found`** (proyecto eliminado):
```json
{
  "detail": "The project no longer exists."
}
```

---

### 2.5 `DELETE /projects/:id` — eliminar

**Supabase query:**
```typescript
supabase
  .from('sig_projects')
  .delete()
  .eq('id', id)
```

**Request del frontend:**
```http
DELETE /api/v1/installations/projects/{id}/
```

**Response `204 No Content`**: Sin body.

**Response `404 Not Found`**:
```json
{
  "detail": "Not found."
}
```

---

### 2.6 `PATCH /projects/:id/name` — renombrar

**Supabase query:**
```typescript
supabase
  .from('sig_projects')
  .update({ name, updated_at: new Date().toISOString() })
  .eq('id', id)
```

**Request del frontend:**
```http
PATCH /api/v1/installations/projects/{id}/name/
Content-Type: application/json

{
  "name": "Nuevo nombre"
}
```

**Response `200 OK`**:
```json
{
  "id": "proj-abc123",
  "name": "Nuevo nombre",
  "updated_at": "2026-05-10T15:00:00.000Z",
  "version": 6
}
```

> Este endpoint actualiza solo el nombre, sin tocar `data` ni el `version`. El frontend lo usa para edits de nombre en la UI sin provocar conflictos de concurrencia.

---

## 3. Realtime — actualizaciones en vivo

El frontend actual usa **Supabase Realtime** (WebSocket sobre PostgreSQL `LISTEN/NOTIFY`) para recibir cambios en la tabla `sig_projects` en tiempo real. Los eventos son:

| Evento Supabase | Descripción | Payload |
|---|---|---|
| `INSERT` | Nuevo proyecto creado por otro usuario | Fila completa del nuevo proyecto |
| `UPDATE` | Proyecto modificado por otro usuario | Fila completa con los nuevos valores |
| `DELETE` | Proyecto eliminado | Solo `{ id: string }` |

**Canal suscrito:**
```
sig_projects_changes  →  tabla: sig_projects, schema: public
sig_project_{id}      →  tabla: sig_projects, filter: id=eq.{id}
```

**Opciones para reemplazar con el backend:**

### Opción A — WebSocket (recomendada)

```
WS /api/v1/installations/projects/realtime/
```

El servidor emite mensajes JSON con la estructura:

```json
{ "event": "INSERT", "data": { <Project object completo> } }
{ "event": "UPDATE", "data": { <Project object completo> } }
{ "event": "DELETE", "data": { "id": "proj-abc123" } }
```

### Opción B — Server-Sent Events (SSE)

```
GET /api/v1/installations/projects/events/
```

Mismo formato de mensajes, sin necesidad de bidireccionalidad.

### Opción C — Polling (implementación mínima)

Si Realtime no está disponible aún, el frontend puede hacer `GET /projects/` cada N segundos y detectar cambios por `updated_at` y `version`. Requiere cambio en el frontend.

> **Prioridad**: Implementar primero los endpoints REST. El realtime puede venir en una segunda fase.

---

## 4. Storage — fotos de Site Surveys

### 4.1 `POST /storage/survey-photos` — subir foto

**Supabase query:**
```typescript
// 1. Upload al bucket 'site-survey-photos'
supabase.storage
  .from('site-survey-photos')
  .upload(path, blob, {
    contentType: blob.type,
    cacheControl: '31536000',
    upsert: false,
  })

// 2. Obtener URL pública
supabase.storage
  .from('site-survey-photos')
  .getPublicUrl(path)
```

**Path generado por el frontend:**
```
{projectId}/{timestamp}-{random6chars}.{ext}
Ejemplo: proj-abc123/1715350800000-k8f2h1.jpg
```

**Request del frontend:**
```http
POST /api/v1/installations/storage/survey-photos/
Content-Type: multipart/form-data

project_id=proj-abc123
photo=<binary JPEG/PNG/WebP/HEIC, máx 8 MB>
```

> El frontend convierte la foto capturada (base64 dataURL) a Blob antes de enviar. El backend recibe el archivo binario.

**Restricciones del frontend:**
- Tamaño máximo: **8 MB**
- Formatos aceptados: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`

**Response `201 Created`:**
```json
{
  "path": "proj-abc123/1715350800000-k8f2h1.jpg",
  "url": "https://cdn.sigtools.com/site-survey-photos/proj-abc123/1715350800000-k8f2h1.jpg"
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `path` | `string` | Ruta relativa del archivo en el storage. Se guarda en el `SiteSurveyMarker.imageUrl` cuando es una ruta, no una URL |
| `url` | `string` | URL pública accesible directamente desde el browser sin auth |

> **Importante**: La `url` devuelta se almacena en el campo `imageUrl` del `SiteSurveyMarker` dentro del `data` del proyecto. Debe ser una URL permanente y pública (sin expiración o con expiración larga).

---

### 4.2 `DELETE /storage/survey-photos` — eliminar foto

**Supabase query:**
```typescript
supabase.storage
  .from('site-survey-photos')
  .remove([path])
```

**Request del frontend:**
```http
DELETE /api/v1/installations/storage/survey-photos/
Content-Type: application/json

{
  "path": "proj-abc123/1715350800000-k8f2h1.jpg"
}
```

**Response `204 No Content`**: Sin body.

---

## 5. Admin — Usuarios

Las siguientes operaciones son para el **panel de administración** de la app. Solo accesibles para usuarios con `access_level = 1`.

### 5.1 `GET /admin/users` — listar usuarios

**Supabase queries (2 queries en paralelo):**

```typescript
// Query 1: perfiles
supabase
  .from('profiles')
  .select('*')
  .order('created_at', { ascending: false })

// Query 2: relaciones usuario-rol con datos del rol
supabase
  .from('user_roles')
  .select('user_id, roles(*)')
```

El frontend luego hace un join en memoria para armar cada `UserWithRoles`.

**Request del frontend:**
```http
GET /api/v1/installations/admin/users/
```

**Response `200 OK`:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "jriascos",
    "full_name": "Juan Riascos",
    "avatar_url": null,
    "is_active": true,
    "email": "jriascos@sig.systems",
    "last_sign_in_at": null,
    "roles": [
      {
        "id": "role-uuid",
        "name": "admin",
        "label": "Administrador",
        "description": "Acceso total al sistema",
        "color": "#6366f1",
        "is_system": true
      }
    ]
  }
]
```

**Estructura `UserWithRoles`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` UUID | ID del usuario |
| `username` | `string` | Nombre de usuario (sin dominio) |
| `full_name` | `string \| null` | Nombre completo |
| `avatar_url` | `string \| null` | URL del avatar |
| `is_active` | `boolean` | Si el usuario está activo |
| `email` | `string` | Construido como `{username}@sig.systems` |
| `last_sign_in_at` | `string \| null` | Último acceso ISO 8601 |
| `roles` | `Role[]` | Array de roles asignados |

---

### 5.2 `POST /admin/users` — crear usuario

**Supabase query:**
```typescript
// Llama una RPC (función PostgreSQL SECURITY DEFINER)
supabase.rpc('admin_create_user', {
  p_email: `${username}@sig.systems`,
  p_password: password,
  p_username: username,
  p_full_name: fullName,
})
// Luego asigna roles con setUserRoles()
```

**Request del frontend:**
```http
POST /api/v1/installations/admin/users/
Content-Type: application/json

{
  "username": "jriascos",
  "password": "contraseña123",
  "full_name": "Juan Riascos",
  "role_names": ["viewer", "surveyor"]
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `username` | `string` | ✅ | Sin dominio. El email se construye como `{username}@sig.systems` |
| `password` | `string` | ✅ | Contraseña inicial |
| `full_name` | `string` | ✅ | Nombre para mostrar |
| `role_names` | `string[]` | ✅ | Array de nombres de roles a asignar (puede ser vacío `[]`) |

**Response `201 Created`:**
```json
{
  "id": "nuevo-uuid",
  "username": "jriascos",
  "full_name": "Juan Riascos",
  "avatar_url": null,
  "is_active": true,
  "email": "jriascos@sig.systems",
  "roles": [
    { "id": "...", "name": "viewer", "label": "Visualizador", ... }
  ]
}
```

**Response `409 Conflict`** (username ya existe):
```json
{
  "detail": "A user with this username already exists."
}
```

---

### 5.3 `PATCH /admin/users/:id` — actualizar usuario

**Supabase queries:**
```typescript
// Actualiza perfil en tabla 'profiles'
supabase
  .from('profiles')
  .update({ full_name, is_active, updated_at })
  .eq('id', userId)

// Reemplaza roles: DELETE + INSERT en user_roles
supabase.from('user_roles').delete().eq('user_id', userId)
supabase.from('user_roles').insert([{ user_id, role_id, granted_by: null }])
```

**Request del frontend:**
```http
PATCH /api/v1/installations/admin/users/{id}/
Content-Type: application/json

{
  "full_name": "Juan Riascos Actualizado",
  "is_active": true,
  "role_names": ["admin"]
}
```

Todos los campos son opcionales — solo se envían los que cambian.

**Response `200 OK`:**
```json
{
  "id": "550e8400...",
  "username": "jriascos",
  "full_name": "Juan Riascos Actualizado",
  "is_active": true,
  "email": "jriascos@sig.systems",
  "roles": [...]
}
```

---

### 5.4 `DELETE /admin/users/:id` — desactivar usuario

**Supabase query:**
```typescript
// No elimina el registro — lo desactiva (soft delete)
supabase
  .from('profiles')
  .update({ is_active: false, updated_at: new Date().toISOString() })
  .eq('id', userId)
```

**Request del frontend:**
```http
DELETE /api/v1/installations/admin/users/{id}/
```

**Response `204 No Content`**: Sin body.

> El frontend hace **soft delete** (desactiva el usuario, no lo elimina). El backend debe implementar el mismo comportamiento: setear `is_active = false`.

---

## 6. Admin — Roles

### 6.1 `GET /admin/roles` — listar roles

**Supabase query:**
```typescript
supabase
  .from('roles')
  .select(`
    *,
    role_permissions (
      permissions (*)
    )
  `)
  .order('created_at')

// Además cuenta usuarios por rol:
supabase.from('user_roles').select('role_id')
```

El frontend hace join en memoria para agregar `user_count`.

**Request del frontend:**
```http
GET /api/v1/installations/admin/roles/
```

**Response `200 OK`:**
```json
[
  {
    "id": "role-uuid",
    "name": "admin",
    "label": "Administrador",
    "description": "Acceso total al sistema",
    "color": "#6366f1",
    "is_system": true,
    "user_count": 3,
    "permissions": [
      {
        "id": "perm-uuid",
        "key": "admin.users.view",
        "label": "Ver usuarios",
        "description": "Permite listar y ver usuarios",
        "app": "installations",
        "category": "admin"
      }
    ]
  }
]
```

**Estructura `RoleWithPermissions`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` UUID | |
| `name` | `string` | Identificador de código (ej: `"admin"`, `"viewer"`) |
| `label` | `string` | Nombre para mostrar |
| `description` | `string \| null` | |
| `color` | `string` | Color hex para la UI |
| `is_system` | `boolean` | Si es un rol del sistema (no se puede eliminar) |
| `user_count` | `integer` | Cantidad de usuarios con este rol |
| `permissions` | `Permission[]` | Permisos asignados a este rol |

---

### 6.2 `POST /admin/roles` — crear rol

**Supabase queries:**
```typescript
// 1. Inserta el rol
supabase.from('roles').insert({ name, label, description, color }).select().single()

// 2. Asigna permisos (DELETE + INSERT en role_permissions)
supabase.from('role_permissions').delete().eq('role_id', roleId)
supabase.from('role_permissions').insert([{ role_id, permission_id }])
```

**Request del frontend:**
```http
POST /api/v1/installations/admin/roles/
Content-Type: application/json

{
  "name": "surveyor",
  "label": "Encuestador de campo",
  "description": "Puede capturar fotos y crear surveys",
  "color": "#10b981",
  "permission_keys": ["installations.surveys.capture", "installations.surveys.view"]
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `name` | `string` | ✅ | Identificador de código, único |
| `label` | `string` | ✅ | Nombre legible |
| `description` | `string` | | Descripción |
| `color` | `string` | ✅ | Color hex |
| `permission_keys` | `string[]` | ✅ | Claves de permisos a asignar (puede ser `[]`) |

**Response `201 Created`:**
```json
{
  "id": "nuevo-role-uuid",
  "name": "surveyor",
  "label": "Encuestador de campo",
  "description": "...",
  "color": "#10b981",
  "is_system": false,
  "user_count": 0,
  "permissions": [...]
}
```

---

### 6.3 `PATCH /admin/roles/:id` — actualizar rol

**Supabase queries:**
```typescript
// Actualiza campos del rol
supabase.from('roles').update({ label, description, color }).eq('id', roleId)

// Reemplaza permisos (solo si se envían)
supabase.from('role_permissions').delete().eq('role_id', roleId)
supabase.from('role_permissions').insert([{ role_id, permission_id }])
```

**Request del frontend:**
```http
PATCH /api/v1/installations/admin/roles/{id}/
Content-Type: application/json

{
  "label": "Nuevo label",
  "color": "#f59e0b",
  "permission_keys": ["installations.surveys.view"]
}
```

Todos los campos son opcionales. Si `permission_keys` no se envía, los permisos actuales no se tocan.

**Response `200 OK`:**
```json
{
  "id": "role-uuid",
  "name": "surveyor",
  "label": "Nuevo label",
  "color": "#f59e0b",
  "is_system": false,
  "user_count": 2,
  "permissions": [...]
}
```

---

### 6.4 `DELETE /admin/roles/:id` — eliminar rol

**Supabase query:**
```typescript
supabase
  .from('roles')
  .delete()
  .eq('id', roleId)
  .eq('is_system', false)   // ← solo permite eliminar roles no-sistema
```

**Request del frontend:**
```http
DELETE /api/v1/installations/admin/roles/{id}/
```

**Response `204 No Content`**: Sin body.

**Response `403 Forbidden`** (intento de eliminar rol del sistema):
```json
{
  "detail": "System roles cannot be deleted."
}
```

---

## 7. Admin — Permisos

### 7.1 `GET /admin/permissions` — listar permisos

**Supabase query:**
```typescript
supabase
  .from('permissions')
  .select('*')
  .order('app')
  .order('category')
  .order('label')
```

**SQL equivalente:**
```sql
SELECT * FROM permissions
ORDER BY app, category, label;
```

**Request del frontend:**
```http
GET /api/v1/installations/admin/permissions/
```

**Response `200 OK`:**
```json
[
  {
    "id": "perm-uuid-1",
    "key": "admin.users.view",
    "label": "Ver usuarios",
    "description": "Permite listar y ver el detalle de usuarios",
    "app": "installations",
    "category": "admin"
  },
  {
    "id": "perm-uuid-2",
    "key": "installations.projects.create",
    "label": "Crear proyectos",
    "description": "Permite crear nuevos proyectos de instalación",
    "app": "installations",
    "category": "projects"
  },
  {
    "id": "perm-uuid-3",
    "key": "installations.projects.delete",
    "label": "Eliminar proyectos",
    "description": null,
    "app": "installations",
    "category": "projects"
  },
  {
    "id": "perm-uuid-4",
    "key": "installations.surveys.capture",
    "label": "Capturar fotos",
    "description": "Permite tomar y subir fotos de campo",
    "app": "installations",
    "category": "surveys"
  },
  {
    "id": "perm-uuid-5",
    "key": "installations.surveys.view",
    "label": "Ver surveys",
    "description": "Permite ver fotos y markers de campo",
    "app": "installations",
    "category": "surveys"
  }
]
```

**Estructura `Permission`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` UUID | |
| `key` | `string` | Identificador de código único. Formato `{app}.{category}.{action}` |
| `label` | `string` | Nombre legible |
| `description` | `string \| null` | Descripción opcional |
| `app` | `string` | Aplicación a la que pertenece (`"installations"`) |
| `category` | `string` | Categoría funcional (`"admin"`, `"projects"`, `"surveys"`) |

**Permission keys actualmente en uso por el frontend:**

| `key` | Descripción |
|---|---|
| `admin.users.view` | Acceder al panel de administración |
| `admin.users.manage` | Crear/editar/eliminar usuarios |
| `installations.projects.create` | Crear nuevos proyectos |
| `installations.projects.delete` | Eliminar proyectos |
| `installations.surveys.capture` | Capturar fotos en campo |
| `installations.surveys.view` | Ver surveys en la sidebar |

---

## 8. Resumen de endpoints

Todos los endpoints requieren cookie `sig_token` válida (salvo los de web-auth).

### Proyectos

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/v1/installations/projects/` | Listar todos los proyectos |
| `POST` | `/api/v1/installations/projects/` | Crear proyecto |
| `GET` | `/api/v1/installations/projects/{id}/` | Obtener proyecto por ID |
| `PATCH` | `/api/v1/installations/projects/{id}/` | Actualizar (con control de versión) |
| `DELETE` | `/api/v1/installations/projects/{id}/` | Eliminar proyecto |
| `PATCH` | `/api/v1/installations/projects/{id}/name/` | Renombrar sin tocar versión |
| `GET/WS` | `/api/v1/installations/projects/realtime/` | Suscripción a cambios en vivo |

### Storage

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/v1/installations/storage/survey-photos/` | Subir foto de campo |
| `DELETE` | `/api/v1/installations/storage/survey-photos/` | Eliminar foto de campo |

### Admin

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/v1/installations/admin/users/` | Listar usuarios |
| `POST` | `/api/v1/installations/admin/users/` | Crear usuario |
| `PATCH` | `/api/v1/installations/admin/users/{id}/` | Actualizar usuario |
| `DELETE` | `/api/v1/installations/admin/users/{id}/` | Desactivar usuario |
| `GET` | `/api/v1/installations/admin/roles/` | Listar roles con permisos |
| `POST` | `/api/v1/installations/admin/roles/` | Crear rol |
| `PATCH` | `/api/v1/installations/admin/roles/{id}/` | Actualizar rol |
| `DELETE` | `/api/v1/installations/admin/roles/{id}/` | Eliminar rol |
| `GET` | `/api/v1/installations/admin/permissions/` | Listar permisos disponibles |

---

## 9. Notas de implementación

### Concurrencia optimista en proyectos

El sistema de versiones es crítico. El flujo es:

```
Cliente tiene versión 5
  │
  ├─ PATCH /projects/abc {expected_version: 5, data: ...}
  │     └─ Backend: UPDATE ... WHERE version=5
  │
  ├─ Versión en DB es 5 → UPDATE exitoso → devuelve versión 6
  │
  └─ Versión en DB es 6 (otro usuario guardó) → 0 filas afectadas
        └─ Backend: responde 409 + objeto "latest" con versión actual
```

### Campo `data` — almacenamiento opaco

El campo `data` de cada proyecto es un JSONB grande (puede pesar varios MB en proyectos complejos). El backend no necesita interpretar su estructura: simplemente almacenar y devolver el JSON íntegro. Recomendación: columna `JSONB` en PostgreSQL o `JSONField` en Django.

### Emails de usuarios admin

El AdminPanel construye el email del usuario como `{username}@sig.systems`. El backend debe respetar esta convención al crear usuarios o devolver el campo `email` con este formato.

### Roles del sistema (`is_system: true`)

Los roles marcados como `is_system = true` no se pueden eliminar (el frontend bloquea el botón y el backend debe rechazar el DELETE con `403`).

### Fotos — URL pública permanente

La URL de las fotos de Site Survey se almacena dentro del JSON del proyecto. Debe ser accesible públicamente desde el browser (sin headers de auth) ya que se carga en etiquetas `<img>`. La URL no debe expirar en el corto plazo.

### `updated_at` — siempre lo fija el servidor

Aunque el frontend envía `updated_at` en los inserts a Supabase (por diseño del cliente), en el backend el servidor debe ignorar cualquier `updated_at` que venga del cliente y usar `NOW()` internamente. Esto evita inconsistencias por diferencias de zona horaria o reloj del cliente.

### Orden de prioridad de implementación

```
1. GET/POST/PATCH/DELETE  /projects/       ← bloqueante para la app
2. POST                   /storage/        ← bloqueante para Site Surveys
3. GET/PATCH/DELETE       /admin/users/    ← panel de admin
4. GET/POST/PATCH/DELETE  /admin/roles/    ← panel de admin
5. GET                    /admin/permissions/ ← panel de admin
6. WebSocket/SSE          /projects/realtime/ ← nice-to-have, reemplaza polling
```
