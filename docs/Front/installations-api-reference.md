# Installations API — Referencia Completa para Frontend

> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación requerida en todos los endpoints.**

---

## Autenticación

Todos los endpoints requieren `IsAuthenticated`. Hay dos mecanismos:

### Opción A — Cookie `sig_token` (recomendada para el panel web)

```ts
// Activar en Axios una sola vez al montar la app
axios.defaults.withCredentials = true
```

La cookie `sig_token` es HttpOnly y se setea automáticamente en el login de SigTools. Si no está presente → `403 Forbidden`.

### Opción B — JWT Bearer Token

```ts
const { data } = await axios.post('/api/v1/web-auth/login/', {
  username: 'hcruz',
  password: '...',
})
// Guardar access_token y adjuntarlo a cada request
axios.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
```

---

## Índice de Endpoints

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET` | `/catalog/cameras/` | Catálogo global de cámaras (jerárquico) |
| `GET` | `/catalog/devices/` | Catálogo global de dispositivos |
| `GET` | `/catalog/vms/` | Lista de VMS disponibles |
| `GET` | `/catalog/installation-types/` | Tipos de instalación |
| `GET` | `/customer-groups/` | Grupos de cliente |
| `GET` | `/users/` | Técnicos IT |
| `GET` | `/users/admins/` | Administradores |
| `GET` | `/users/project-owners/` | Project Owners |
| `GET` | `/users/lead-techs/` | Lead Techs |
| `GET` | `/users/developers/` | Desarrolladores |
| `GET` | `/sites/` | Lista de todos los sitios activos |
| `POST` | `/sites/` | Crear un nuevo sitio |
| `DELETE` | `/sites/<site_id>/` | Eliminar un sitio |
| `GET` | `/sites/<site_id>/status/` | Estado de instalaciones del sitio |
| `GET` | `/sites/<site_id>/inventory/` | Inventario del sitio |
| `GET` | `/sites/<site_id>/catalog/` | Cámaras instaladas en el sitio |
| `GET` | `/sites/<site_id>/catalog/switches/` | Switches instalados en el sitio |
| `POST` | `/projects/` | Crear instalación (proyecto) |
| `DELETE` | `/projects/<inst_id>/` | Eliminar instalación |

---

## 1. Catálogos Globales

### `GET /catalog/cameras/`

Retorna la estructura jerárquica de cámaras: **Tipo → Marca → [Modelos]**.  
Útil para armar selectores de cámaras al crear instalaciones.

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "name": "Bullet",
    "description": "Cámara exterior tipo bala",
    "lens_amount": 1,
    "brands": [
      {
        "id": 3,
        "name": "HIKVISION",
        "models": [
          { "id": 12, "name": "DS-2CD2143G2-I" },
          { "id": 14, "name": "DS-2CD2347G2-LU" }
        ]
      }
    ]
  }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `number` | ID del tipo de cámara |
| `name` | `string` | Nombre del tipo (`"Bullet"`, `"Dome"`, `"PTZ"`, …) |
| `description` | `string \| null` | Descripción larga del tipo |
| `lens_amount` | `number` | Cantidad de lentes del tipo |
| `brands[].id` | `number` | ID de la marca |
| `brands[].name` | `string` | Nombre de la marca en mayúsculas |
| `brands[].models[].id` | `number` | ID del modelo |
| `brands[].models[].name` | `string` | Nombre del modelo |

---

### `GET /catalog/devices/`

Lista plana de todos los tipos de dispositivos (switches, NVRs, routers, etc.).

**Response `200 OK`:**

```json
[
  { "id": 5, "device_type": "Switch", "brand": "Cisco", "model": "SG350-10" },
  { "id": 9, "device_type": "NVR",    "brand": "Hikvision", "model": "DS-7616NI-K2" }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `number` | ID del tipo de dispositivo |
| `device_type` | `string` | Categoría (`"Switch"`, `"NVR"`, `"Router"`, …) |
| `brand` | `string` | Marca del dispositivo |
| `model` | `string` | Modelo del dispositivo |

---

### `GET /catalog/vms/`

Lista de nombres de VMS únicos registrados en la DB.

**Response `200 OK`:**

```json
["Avigilon", "Milestone", "Nx Witness"]
```

Retorna un arreglo de strings ordenado alfabéticamente.

---

### `GET /catalog/installation-types/`

Tipos de instalación disponibles para usar en proyectos.

**Response `200 OK`:**

```json
[
  { "id": 1, "name": "Nueva instalación" },
  { "id": 2, "name": "Ampliación" }
]
```

---

## 2. Customer Groups

### `GET /customer-groups/`

**Response `200 OK`:**

```json
[
  { "id": 4, "name": "Asbury Automotive" },
  { "id": 7, "name": "SIG Direct" }
]
```

---

## 3. Usuarios

Todos los endpoints de usuarios devuelven el mismo shape:

```json
[
  { "id": 12, "username": "jsmith", "name": "John Smith", "role": "IT Technician" }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `number` | ID del usuario |
| `username` | `string \| null` | Username de login |
| `name` | `string` | Nombre completo |
| `role` | `string` | Rol asignado |

### Endpoints disponibles

| URL | Rol devuelto |
|-----|-------------|
| `GET /users/` | IT Technicians (default) |
| `GET /users/it-technicians/` | IT Technicians |
| `GET /users/admins/` | Admin |
| `GET /users/project-owners/` | Project Owner |
| `GET /users/lead-techs/` | Lead Tech |
| `GET /users/developers/` | Developer |

---

## 4. Sitios

### `GET /sites/`

Lista todos los sitios activos (no eliminados), ordenados por nombre.

**Response `200 OK`:**

```json
[
  {
    "id": 305,
    "name": "AS 3281 Storage Lot",
    "location": "Dallas, TX",
    "address": "3281 Manor Way, Dallas, TX 75235"
  },
  {
    "id": 124,
    "name": "AS Audi of North Atlanta",
    "location": "Roswell, GA",
    "address": "11505 Alpharetta Hwy,\r\nRoswell, GA 30076"
  }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `number` | ID del sitio — usar como `site_id` en otros endpoints |
| `name` | `string` | Nombre del sitio |
| `location` | `string \| null` | Ciudad y estado (`"Dallas, TX"`). `null` si no tiene ciudad ni estado. |
| `address` | `string \| null` | Dirección física para mapas. Puede tener `\r\n` → limpiar con `.replace(/\r\n/g, ', ')`. `null` si no tiene. |

> **Nota limpieza de address en TypeScript:**
> ```ts
> const cleanAddress = (addr: string | null) =>
>   addr?.replace(/\r\n/g, ', ').trim() ?? null
> ```

---

### `POST /sites/`

Crea un nuevo sitio en `sigtools_beta`.

**Request body:**

```json
{
  "name": "Nuevo Sitio Dallas",
  "customer_group_id": 4,
  "ip_address": "192.168.1.100",
  "teams_channelid": "",
  "teams_teamid": ""
}
```

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `name` | `string (max 255)` | ✅ | — | Nombre del sitio |
| `customer_group_id` | `number` | ✅ | — | ID del grupo cliente (ver `/customer-groups/`) |
| `ip_address` | `string (IP)` | ❌ | `"0.0.0.0"` | IP de red del sitio |
| `teams_channelid` | `string (max 255)` | ❌ | `""` | ID del canal de Teams |
| `teams_teamid` | `string (max 255)` | ❌ | `""` | ID del equipo de Teams |

**Response `201 Created`:**

```json
{ "site_id": 312 }
```

---

### `DELETE /sites/<site_id>/`

Elimina un sitio y todas sus instalaciones (soft-delete).

**Response `200 OK`:**
```json
{ "success": true, "message": "Site 312 and its installations deleted." }
```

**Response `404 Not Found`:**
```json
{ "detail": "Site not found or already deleted." }
```

---

### `GET /sites/<site_id>/status/`

Retorna el estado de las instalaciones del sitio.

**Response `200 OK`:**

```json
{
  "site_id": 159,
  "installations": [
    { "installation_id": 44, "type_name": "Nueva instalación", "status_name": "Activo" },
    { "installation_id": 89, "type_name": "Ampliación", "status_name": "En progreso" }
  ]
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `installation_id` | `number` | ID de la instalación |
| `type_name` | `string` | Tipo de instalación |
| `status_name` | `string` | Estado actual |

**Response `404`** si `site_id` no existe.

---

### `GET /sites/<site_id>/inventory/`

Conteo de equipos instalados por categoría, marca y modelo.

**Response `200 OK`:**

```json
{
  "site_id": 159,
  "inventory": [
    { "category": "camera", "brand": "HIKVISION", "model": "DS-2CD2143G2-I", "qty": 12 },
    { "category": "camera", "brand": "DAHUA",     "model": "N43AF5Z",         "qty": 3  },
    { "category": "switch", "brand": "Cisco",     "model": "SG350-10",        "qty": 2  }
  ]
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `category` | `string` | `"camera"` o `"switch"` |
| `brand` | `string \| null` | Marca del equipo |
| `model` | `string \| null` | Modelo del equipo |
| `qty` | `number` | Cantidad instalada |

---

### `GET /sites/<site_id>/catalog/`

Retorna **cada cámara individual** instalada en el sitio con su número de serie.  
Una misma unidad de equipo = una entrada en la lista.

**Response `200 OK`:**

```json
[
  {
    "id": "cam-7",
    "name": "N43AF5Z",
    "brand": "DAHUA",
    "serial": "2G01234567",
    "resolution": null,
    "type": "Exterior bullet",
    "category": "camera",
    "subtype": "bullet",
    "lensType": null,
    "rango_lente_mm": null,
    "rango_fov_grados": null,
    "poe_watts": null,
    "bandwidth_mbps": null
  }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `string` | ID único con prefijo `cam-`. Ej: `"cam-7"` |
| `name` | `string` | Nombre del modelo de cámara |
| `brand` | `string` | Marca en MAYÚSCULAS |
| `serial` | `string \| null` | Número de serie físico de la unidad |
| `resolution` | `null` | No disponible en DB actualmente |
| `type` | `string \| null` | Descripción del tipo de cámara |
| `category` | `"camera"` | Siempre `"camera"` |
| `subtype` | `string` | Tipo en minúsculas: `"bullet"`, `"dome"`, `"ptz"`, … |
| `lensType` | `null` | No disponible en DB actualmente |
| `rango_lente_mm` | `null` | No disponible en DB actualmente |
| `rango_fov_grados` | `null` | No disponible en DB actualmente |
| `poe_watts` | `null` | No disponible en DB actualmente |
| `bandwidth_mbps` | `null` | No disponible en DB actualmente |

Sitio sin cámaras → `[]` con status `200`.

---

### `GET /sites/<site_id>/catalog/switches/`

Retorna los **modelos distintos** de switches instalados en el sitio (no unidades individuales).

**Response `200 OK`:**

```json
[
  {
    "id": "switch-5",
    "name": "SG350-10",
    "brand": "Cisco",
    "resolution": "—",
    "type": null,
    "category": "static",
    "subtype": "switch",
    "poe_watts": null,
    "bandwidth_mbps": null,
    "poe_budget_watts": null,
    "uplink_mbps": null
  }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `string` | ID con prefijo `switch-`. Ej: `"switch-5"` |
| `name` | `string` | Nombre del modelo |
| `brand` | `string` | Marca del switch |
| `resolution` | `"—"` | Siempre `"—"` (no aplica para switches) |
| `type` | `null` | No disponible |
| `category` | `"static"` | Siempre `"static"` |
| `subtype` | `"switch"` | Siempre `"switch"` |
| `poe_watts` | `null` | No disponible en DB actualmente |
| `bandwidth_mbps` | `null` | No disponible en DB actualmente |
| `poe_budget_watts` | `null` | No disponible en DB actualmente |
| `uplink_mbps` | `null` | No disponible en DB actualmente |

---

## 5. Proyectos (Instalaciones)

### `POST /projects/`

Crea una nueva instalación vinculada a un sitio.

**Request body:**

```json
{
  "site_id": 159,
  "installation_type_id": 1,
  "inst_status_id": 1,
  "pm_id": 12,
  "lead_tech_id": 7,
  "technician_id": 3,
  "vms": "Milestone",
  "nvr_brand": "Hikvision",
  "nvr_model": "DS-7616NI-K2",
  "network_switch_brand": "Cisco",
  "network_switch_model": "SG350-10",
  "router_brand": "Ubiquiti",
  "router_model": "ERX",
  "cameras_count": 24,
  "notes": "Instalación perimetral"
}
```

**Response `201 Created`:**

```json
{ "installation_id": 91 }
```

---

### `DELETE /projects/<inst_id>/`

Elimina una instalación (soft-delete).

**Response `200 OK`:**
```json
{ "success": true, "message": "Installation 91 deleted." }
```

**Response `404`:**
```json
{ "detail": "Installation not found or already deleted." }
```

---

## Manejo de Errores

| Status | Causa | Acción |
|--------|-------|--------|
| `400 Bad Request` | Body inválido / campo requerido faltante | Mostrar `error.response.data` al usuario |
| `403 Forbidden` | Sin cookie o token expirado | Redirigir a login |
| `404 Not Found` | `site_id` o `inst_id` no existe | Mostrar mensaje "Sitio no encontrado" |
| `500` | Error interno del servidor | Log en consola, mensaje genérico al usuario |

---

## Ejemplo de Integración — Cargar sitios con mapa

```ts
interface Site {
  id: number
  name: string
  location: string | null
  address: string | null
}

const cleanAddress = (addr: string | null): string | null =>
  addr?.replace(/\r\n/g, ', ').trim() ?? null

async function loadSites(): Promise<Site[]> {
  const { data } = await axios.get<Site[]>('/api/v1/installations/sites/')
  return data.map(site => ({
    ...site,
    address: cleanAddress(site.address),
  }))
}
```

## Ejemplo de Integración — Catálogo completo de un sitio

```ts
// Cargar cámaras y switches en paralelo
const [cameras, switches] = await Promise.all([
  axios.get(`/api/v1/installations/sites/${siteId}/catalog/`),
  axios.get(`/api/v1/installations/sites/${siteId}/catalog/switches/`),
])

const catalog = [...cameras.data, ...switches.data]
// Distinguir por item.category: "camera" | "static"
// Distinguir por item.subtype: "bullet" | "dome" | "ptz" | "switch" | ...
```
