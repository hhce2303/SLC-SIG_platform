

# Installations API — Guía para Frontend

> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación:** Cookie `sig_token` (obtenida al hacer login con `sigtools_auth`)

---

## Autenticación

Todos los endpoints requieren la cookie `sig_token` activa.  
Esta se setea automáticamente en el login. En el cliente HTTP simplemente incluye las cookies:

```ts
// Axios global
axios.defaults.withCredentials = true

// Fetch nativo
fetch(url, { credentials: 'include' })
```

Si la cookie no está presente o expiró, el servidor responde `403 Forbidden`.

---

## Endpoints disponibles

### 1. Lista de proyectos tácticos

```
GET /sig-projects/
```

Retorna todos los proyectos canvas ordenados por fecha de modificación (más reciente primero).

**Response `200`:**
```json
[
  {
    "id": "c7f0bab2-c01c-4b9a-9e16-e2241bdf6e94",
    "name": "Ken Garff Big Star Cadillac",
    "updated_at": "2026-05-04T14:22:59.934000+00:00",
    "version": 1,
    "data": {
      "sitios": [...],
      "devices": [...],
      "enlaces": [...],
      "drawings": [...]
    }
  }
]
```

---

### 2. Detalle de un proyecto

```
GET /sig-projects/<uuid>/
```

**Params:** `uuid` — el `id` del proyecto (UUID string)

**Response `200`:** mismo shape que el item de la lista

**Response `404`:**
```json
{ "detail": "Not found." }
```

---

### 3. Usuarios con sus roles

```
GET /admin/users/
```

Retorna todos los usuarios activos del sistema con los roles asignados.

**Response `200`:**
```json
[
  {
    "id": 67,
    "name": "Test Admin",
    "username": "test",
    "email": "test@sig.systems",
    "is_active": true,
    "created_at": "2026-05-10T12:47:37",
    "roles": [
      {
        "id": "ed87e26e-8a95-427f-a9e7-d070ab2a342d",
        "name": "admin",
        "label": "Administrador",
        "description": "Acceso total al sistema",
        "color": "#ef4444",
        "is_system": true
      }
    ]
  }
]
```

> `roles` es un array vacío `[]` si el usuario no tiene rol asignado.  
> `is_system: true` indica que el rol es predefinido y no puede eliminarse.

---

### 4. Roles con permisos

```
GET /admin/roles/
```

Retorna todos los roles con sus permisos asignados y el conteo de usuarios.

**Response `200`:**
```json
[
  {
    "id": "ed87e26e-8a95-427f-a9e7-d070ab2a342d",
    "name": "admin",
    "label": "Administrador",
    "description": "Acceso total al sistema",
    "color": "#ef4444",
    "is_system": true,
    "user_count": 5,
    "permissions": [
      {
        "id": "7175e6cb-dfa4-4314-a507-8636dca9befa",
        "key": "installations.projects.view",
        "label": "Ver proyectos",
        "description": "Ver lista de proyectos",
        "app": "installations",
        "category": "Proyectos"
      }
    ]
  }
]
```

> `permissions` es `[]` si el rol no tiene permisos asignados.

---

### 5. Catálogo de permisos

```
GET /admin/permissions/
```

Retorna todos los permisos disponibles en el sistema, ordenados por `app → category → label`.

**Response `200`:**
```json
[
  {
    "id": "47955be1-2607-4803-92b0-3e7bdb8fa586",
    "key": "admin.users.view",
    "label": "Ver usuarios",
    "description": "Ver lista de usuarios del sistema",
    "app": "admin",
    "category": "Usuarios"
  }
]
```

**Apps actuales:** `admin`, `installations`, `inventory`

---

## Estructura del campo `data` (sig_projects)

```ts
interface ProjectData {
  sitios: Sitio[]
  devices: Device[]
  enlaces: Enlace[]
  drawings: any[]
}

interface Sitio {
  id: string        // UUID
  lat: number
  lng: number
  zoom: number
  nombre: string
}

interface Device {
  instanceId: string
  catalogoId: string
  sitioId: string
  lat: number
  lng: number
  numero: number
  displayLabel: string
  rotacionBase: number
  area: string
  varifocal_mm?: number
  alcance_metros?: number
}

interface Enlace {
  id: string
  tipo: "cable" | "wireless"
  sitioId: string
  sourceId: string  // instanceId origen
  targetId: string  // instanceId destino
}
```

---

## Resumen de permisos por app

| `key` | `label` | `category` |
|---|---|---|
| `admin.users.view` | Ver usuarios | Usuarios |
| `admin.users.create` | Crear usuarios | Usuarios |
| `admin.users.edit` | Editar usuarios | Usuarios |
| `admin.users.delete` | Eliminar usuarios | Usuarios |
| `admin.roles.manage` | Gestionar roles | Roles |
| `admin.permissions.manage` | Gestionar permisos | Permisos |
| `installations.projects.view` | Ver proyectos | Proyectos |
| `installations.projects.create` | Crear proyectos | Proyectos |
| `installations.projects.edit` | Editar proyectos | Proyectos |
| `installations.projects.delete` | Eliminar proyectos | Proyectos |
| `installations.map.view` | Ver mapa táctico | Mapa |
| `installations.map.edit` | Editar mapa | Mapa |
| `installations.inventory.export` | Exportar a inventario | Inventario |
| `installations.surveys.view` | Ver Site Surveys | Site Surveys |
| `installations.surveys.capture` | Capturar fotos | Site Surveys |
| `installations.surveys.realtime` | Monitor en tiempo real | Site Surveys |
| `installations.pdf.view` | Ver PDF Editor | PDF Editor |
| `inventory.view` | Ver inventario | Inventario |
| `inventory.create` | Crear artículos | Inventario |
| `inventory.edit` | Editar artículos | Inventario |
| `inventory.delete` | Eliminar artículos | Inventario |
| `inventory.reports.view` | Ver reportes | Reportes |
| `inventory.companies.manage` | Gestionar empresas | Empresas |

---

## Notas

- Todos los `id` de **roles** y **permisos** son UUID (string).
- Los `id` de **usuarios** son enteros (bigint).
- Los `id` de **sig_projects** son UUID (string).
- El campo `is_active` en usuarios es `boolean`.
- El campo `is_system` en roles es `boolean`. Los roles `is_system: true` no deben permitir eliminación en el UI.
- `sig_projects` empieza vacía — el frontend la pobla cuando guarda proyectos.
