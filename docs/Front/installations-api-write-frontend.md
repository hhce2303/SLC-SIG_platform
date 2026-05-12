# Installations API — Endpoints de Escritura (Frontend Guide)

> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación:** Cookie `sig_token` (HttpOnly, se setea automáticamente en el login)

```ts
// Requerido en todas las llamadas
axios.defaults.withCredentials = true
```

Si la cookie no está presente o expiró → `403 Forbidden`.

---

## Índice

1. [sig_projects — Proyectos canvas](#1-sig_projects--proyectos-canvas)
   - [POST /sig-projects/](#11-post-sig-projects--crear-proyecto)
   - [PATCH /sig-projects/\<uuid\>/](#12-patch-sig-projectsuuid--actualizar-proyecto)
   - [DELETE /sig-projects/\<uuid\>/](#13-delete-sig-projectsuuid--eliminar-proyecto)
   - [PATCH /sig-projects/\<uuid\>/name/](#14-patch-sig-projectsuuidname--renombrar-proyecto)
2. [Admin — Usuarios](#2-admin--usuarios)
   - [POST /admin/users/](#21-post-adminusers--crear-usuario)
   - [PATCH /admin/users/\<id\>/](#22-patch-adminusersid--actualizar-usuario)
   - [DELETE /admin/users/\<id\>/](#23-delete-adminusersid--desactivar-usuario)
3. [Admin — Roles](#3-admin--roles)
   - [POST /admin/roles/](#31-post-adminroles--crear-rol)
   - [PATCH /admin/roles/\<uuid\>/](#32-patch-adminrolesuuid--actualizar-rol)
   - [DELETE /admin/roles/\<uuid\>/](#33-delete-adminrolesuuid--eliminar-rol)

---

## 1. sig_projects — Proyectos canvas

### 1.1 `POST /sig-projects/` — Crear proyecto

Crea un nuevo proyecto canvas. El frontend **puede** enviar su propio UUID; si no lo envía el backend genera uno.

**Request body:**

```json
{
  "id": "c7f0bab2-c01c-4b9a-9e16-e2241bdf6e94",
  "name": "Ken Garff Big Star Cadillac",
  "data": {
    "sitios": [],
    "devices": [],
    "enlaces": [],
    "drawings": []
  }
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `id` | UUID string | No | UUID del proyecto. Si se omite, el backend genera uno. |
| `name` | string | **Sí** | Nombre del proyecto (max 255 chars). |
| `data` | object | No | Estado inicial del canvas. Por defecto `{}`. |

**Response `201 Created`:**

```json
{
  "id": "c7f0bab2-c01c-4b9a-9e16-e2241bdf6e94",
  "name": "Ken Garff Big Star Cadillac",
  "updated_at": "2026-05-10T14:22:59.934000",
  "version": 1,
  "data": { "sitios": [], "devices": [], "enlaces": [], "drawings": [] }
}
```

**Response `409 Conflict`** — UUID ya existe:

```json
{ "detail": "A project with this ID already exists." }
```

**Patrón en el frontend:**

```ts
const res = await axios.post('/sig-projects/', {
  id: crypto.randomUUID(),   // genera el UUID en el cliente
  name: 'Nuevo Proyecto',
  data: { sitios: [], devices: [], enlaces: [], drawings: [] },
})
const project = res.data  // shape: SigProject
```

---

### 1.2 `PATCH /sig-projects/<uuid>/` — Actualizar proyecto

Actualiza `name` + `data` completos con **control de concurrencia optimista** vía `expected_version`.

> El campo `version` se incrementa automáticamente en cada PATCH exitoso.  
> Si otro cliente guardó antes que tú, recibirás `409` con el estado actual del proyecto.

**Params:** `uuid` — el `id` del proyecto

**Request body:**

```json
{
  "name": "Ken Garff Big Star Cadillac (v2)",
  "data": {
    "sitios": [...],
    "devices": [...],
    "enlaces": [...],
    "drawings": [...]
  },
  "expected_version": 1
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `name` | string | **Sí** | Nombre del proyecto. |
| `data` | object | **Sí** | Estado completo del canvas. |
| `expected_version` | integer ≥ 1 | **Sí** | Versión que el cliente espera patchear. Debe coincidir con la actual en DB. |

**Response `200 OK`:**

```json
{
  "id": "c7f0bab2-c01c-4b9a-9e16-e2241bdf6e94",
  "name": "Ken Garff Big Star Cadillac (v2)",
  "updated_at": "2026-05-10T15:00:00.000000",
  "version": 2,
  "data": { ... }
}
```

**Response `409 Conflict`** — versión diferente a la actual en DB:

```json
{
  "detail": "Version conflict. Project was modified by another session.",
  "latest": {
    "id": "c7f0bab2-c01c-4b9a-9e16-e2241bdf6e94",
    "name": "Ken Garff (modificado por otra sesión)",
    "updated_at": "2026-05-10T14:55:00.000000",
    "version": 2,
    "data": { ... }
  }
}
```

> Usa `latest` para mostrar al usuario el estado más reciente y preguntarle si desea sobrescribir.

**Response `404 Not Found`:**

```json
{ "detail": "Not found." }
```

**Patrón en el frontend:**

```ts
try {
  const res = await axios.patch(`/sig-projects/${project.id}/`, {
    name: project.name,
    data: project.data,
    expected_version: project.version,
  })
  setProject(res.data)  // actualiza con la nueva version
} catch (err) {
  if (err.response?.status === 409) {
    const latest = err.response.data.latest
    // mostrar modal de conflicto con `latest`
  }
}
```

---

### 1.3 `DELETE /sig-projects/<uuid>/` — Eliminar proyecto

Elimina permanentemente un proyecto (hard delete).

**Params:** `uuid` — el `id` del proyecto

**Response `204 No Content`** — eliminado exitosamente. Sin body.

**Response `404 Not Found`:**

```json
{ "detail": "Not found." }
```

---

### 1.4 `PATCH /sig-projects/<uuid>/name/` — Renombrar proyecto

Actualiza **solo el nombre** del proyecto. **No incrementa `version`** — útil para renombrar sin perder la sesión de edición del canvas.

**Params:** `uuid` — el `id` del proyecto

**Request body:**

```json
{ "name": "Nuevo nombre del proyecto" }
```

| Campo | Tipo | Requerido |
|---|---|---|
| `name` | string (max 255) | **Sí** |

**Response `200 OK`:**

```json
{
  "id": "c7f0bab2-c01c-4b9a-9e16-e2241bdf6e94",
  "name": "Nuevo nombre del proyecto",
  "updated_at": "2026-05-10T15:05:00.000000",
  "version": 2,
  "data": { ... }
}
```

**Response `404 Not Found`:**

```json
{ "detail": "Not found." }
```

---

## 2. Admin — Usuarios

### 2.1 `POST /admin/users/` — Crear usuario

Crea un usuario en `sigtools_beta.users` y asigna roles por nombre.

> El email se genera automáticamente como `{username}@sig.systems`.

**Request body:**

```json
{
  "username": "jsmith",
  "password": "s3cur3P@ss",
  "full_name": "John Smith",
  "role_names": ["viewer", "installations-editor"]
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `username` | string | **Sí** | Nombre de usuario único. |
| `password` | string ≥ 6 chars | **Sí** | Contraseña. Se almacena hasheada. No se devuelve nunca. |
| `full_name` | string | **Sí** | Nombre completo del usuario. |
| `role_names` | string[] | No | Nombres de roles a asignar (deben existir en `app_roles.name`). Por defecto `[]`. |

**Response `201 Created`:**

```json
{
  "id": 72,
  "name": "John Smith",
  "username": "jsmith",
  "email": "jsmith@sig.systems",
  "is_active": true,
  "created_at": "2026-05-10T15:10:00",
  "roles": [
    {
      "id": "some-uuid",
      "name": "viewer",
      "label": "Viewer",
      "description": "",
      "color": "#6366f1",
      "is_system": false
    }
  ]
}
```

**Response `409 Conflict`** — username ya existe:

```json
{ "detail": "A user with this username already exists." }
```

**Response `400 Bad Request`** — validación fallida:

```json
{
  "username": ["This field is required."],
  "password": ["Ensure this field has at least 6 characters."]
}
```

---

### 2.2 `PATCH /admin/users/<id>/` — Actualizar usuario

Actualiza el nombre y/o los roles de un usuario. **Solo se requiere enviar los campos a cambiar** (mínimo uno).

**Params:** `id` — el ID numérico del usuario

**Request body (todos opcionales, mínimo uno):**

```json
{
  "full_name": "John A. Smith",
  "role_names": ["admin"]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `full_name` | string | Nuevo nombre completo. |
| `role_names` | string[] | **Reemplaza** todos los roles del usuario. Enviar `[]` para quitar todos los roles. |

> ⚠️ `role_names` hace un **reemplazo completo**, no una suma. Si envías `["admin"]`, el usuario quedará solo con ese rol aunque antes tuviera más.

**Response `200 OK`:** mismo shape que `POST /admin/users/` (usuario completo con roles).

**Response `404 Not Found`:**

```json
{ "detail": "User not found." }
```

**Response `400 Bad Request`** — body vacío (sin campos):

```json
{ "non_field_errors": ["At least one field must be provided."] }
```

---

### 2.3 `DELETE /admin/users/<id>/` — Desactivar usuario

**Soft delete:** pone `deleted_at = NOW()`. El usuario deja de aparecer en `GET /admin/users/` y no puede autenticarse.

**Params:** `id` — el ID numérico del usuario

**Response `200 OK`:**

```json
{
  "success": true,
  "message": "User 72 deactivated."
}
```

**Response `404 Not Found`** — usuario no existe o ya está inactivo:

```json
{ "detail": "User not found or already inactive." }
```

---

## 3. Admin — Roles

### 3.1 `POST /admin/roles/` — Crear rol

Crea un rol en `sigtools_beta.app_roles` y asigna permisos por `key`.

**Request body:**

```json
{
  "name": "installations-editor",
  "label": "Editor de Instalaciones",
  "description": "Puede crear y editar proyectos canvas",
  "color": "#10b981",
  "permission_keys": [
    "installations.projects.view",
    "installations.projects.edit"
  ]
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `name` | string | **Sí** | Identificador único del rol (slug, ej: `installations-editor`). |
| `label` | string | **Sí** | Nombre legible en la UI. |
| `description` | string | No | Descripción del rol. Por defecto `""`. |
| `color` | string | No | Color hex para la UI. Por defecto `"#6366f1"`. |
| `permission_keys` | string[] | No | Keys de los permisos a asignar (deben existir). Por defecto `[]`. |

**Response `201 Created`:**

```json
{
  "id": "d9f1a3b2-0001-4c88-8e77-aabbccdd1122",
  "name": "installations-editor",
  "label": "Editor de Instalaciones",
  "description": "Puede crear y editar proyectos canvas",
  "color": "#10b981",
  "is_system": false,
  "user_count": 0,
  "permissions": [
    {
      "id": "perm-uuid",
      "key": "installations.projects.view",
      "label": "Ver proyectos",
      "description": "...",
      "app": "installations",
      "category": "Proyectos"
    }
  ]
}
```

**Response `409 Conflict`** — nombre de rol ya existe:

```json
{ "detail": "A role with this name already exists." }
```

---

### 3.2 `PATCH /admin/roles/<uuid>/` — Actualizar rol

Actualiza el `label`, `description`, `color` y/o permisos de un rol. **Solo se requiere enviar los campos a cambiar** (mínimo uno).

**Params:** `uuid` — el `id` del rol

**Request body (todos opcionales, mínimo uno):**

```json
{
  "label": "Editor de Proyectos",
  "color": "#f59e0b",
  "permission_keys": [
    "installations.projects.view",
    "installations.projects.edit",
    "installations.projects.delete"
  ]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `label` | string | Nuevo label visible. |
| `description` | string | Nueva descripción. |
| `color` | string | Nuevo color hex. |
| `permission_keys` | string[] | **Reemplaza** todos los permisos del rol. Enviar `[]` para quitar todos. |

> ⚠️ `permission_keys` hace **reemplazo completo**, no suma.

**Response `200 OK`:** mismo shape que `POST /admin/roles/` (rol completo con permisos y `user_count`).

**Response `404 Not Found`:**

```json
{ "detail": "Role not found." }
```

**Response `400 Bad Request`** — body vacío:

```json
{ "non_field_errors": ["At least one field must be provided."] }
```

---

### 3.3 `DELETE /admin/roles/<uuid>/` — Eliminar rol

Elimina un rol permanentemente junto con sus asignaciones de permisos y usuarios.

> Los roles con `is_system: true` **no pueden eliminarse** — retorna `409`.

**Params:** `uuid` — el `id` del rol

**Response `200 OK`:**

```json
{
  "success": true,
  "message": "Role d9f1a3b2-0001-4c88-8e77-aabbccdd1122 deleted."
}
```

**Response `409 Conflict`** — rol de sistema:

```json
{ "detail": "System roles cannot be deleted." }
```

**Response `404 Not Found`:**

```json
{ "detail": "Role not found." }
```

---

## Resumen de status codes

| Código | Significado |
|---|---|
| `200 OK` | Operación exitosa con body de respuesta. |
| `201 Created` | Recurso creado. Body contiene el recurso completo. |
| `204 No Content` | Eliminado exitosamente. Sin body. |
| `400 Bad Request` | Validación fallida. Body contiene errores de campo. |
| `403 Forbidden` | Sin cookie / token expirado. |
| `404 Not Found` | Recurso no encontrado. |
| `409 Conflict` | Conflicto: ID duplicado, versión desactualizada o rol de sistema. |

---

## TypeScript — Tipos de referencia

```ts
interface SigProject {
  id: string           // UUID
  name: string
  updated_at: string   // ISO 8601
  version: number
  data: ProjectData
}

interface AdminUser {
  id: number
  name: string
  username: string
  email: string
  is_active: boolean
  created_at: string   // ISO 8601
  roles: AdminRoleNested[]
}

interface AdminRoleNested {
  id: string           // UUID
  name: string         // slug
  label: string
  description: string | null
  color: string | null
  is_system: boolean
}

interface AdminRole {
  id: string           // UUID
  name: string         // slug
  label: string
  description: string | null
  color: string | null
  is_system: boolean
  user_count: number
  permissions: AdminPermission[]
}

interface AdminPermission {
  id: string
  key: string
  label: string
  description: string | null
  app: string
  category: string
}
```
