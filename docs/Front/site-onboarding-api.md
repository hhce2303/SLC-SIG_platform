# Site Onboarding API — Guía para el Frontend

> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación:** Cookie `sig_token` (HttpOnly) o Bearer Token JWT

```ts
// Requerido en todas las llamadas
axios.defaults.withCredentials = true
```

---

## ⚠️ Aclaración de nombres de campos (2026-05)

El frontend actualmente envía los campos **correctos**. Hay una discrepancia entre el
`API_CONTRACTS.md` interno del frontend y el backend real. **El backend es la fuente de verdad.**

| Campo que envía el frontend | Campo en el backend | Estado |
|---|---|---|
| `name` | `name` | ✅ Correcto |
| `it_lead_tech_id` | `it_lead_tech_id` | ✅ Correcto |
| `project_owner` | `project_owner` | ✅ Correcto |
| `starting_date` | `starting_date` | ✅ Correcto |
| `limit_date` | `limit_date` | ✅ Correcto |

> Los nombres en `API_CONTRACTS.md` del frontend (`site_name`, `lead_tech_id`,
> `project_owner_id`, `start_date`, `end_date`) **no son los que usa el backend**.
> No cambiar el frontend — ya está correcto.

---

## ⚠️ Cambio arquitectural importante (2026-05)

### ¿Qué cambió y por qué?

Antes, `POST /onboarding/` creaba el sitio directamente en la tabla `sites` de producción.
Ahora crea un **sitio en etapa de pre-verificación** (`project_sites`), que debe pasar filtros
de verificación y autorización antes de ser promovido a la tabla `sites` oficial.

**¿Por qué?**  
Los sitios nuevos necesitan ser revisados (datos correctos, grupo de cliente válido, técnico
asignado, etc.) antes de aparecer en el dashboard principal. Un sitio incorrecto en `sites`
contamina reportes, inventario y asignaciones.

### ¿Qué NO cambió para el frontend?

- El contrato del request de `POST /onboarding/` es **idéntico** — mismos campos, mismas reglas.
- El contrato del response de `POST /onboarding/` es **idéntico** — mismos campos devueltos.
- Los campos `installation_id` y `site_id` siguen llegando y funcionan igual para navegar
  al detalle de la instalación.

### ¿Qué SÍ cambia en el comportamiento visible?

| Antes | Ahora |
|---|---|
| El sitio aparecía en el dashboard de sites inmediatamente | El sitio **no aparece** en el dashboard principal hasta ser aprobado |
| `site_id` apuntaba a `sites` | `site_id` apunta a `project_sites` (staging) |
| No había estado de verificación | El sitio tiene `verification_status: "pending"` al crearse |

---

## Flujo completo nuevo

```
1. POST /onboarding/
   → Crea project_site (verification_status: "pending")
   → Crea installation vinculada al project_site
   → Retorna installation_id + site_id (del project_site)
        ↓
2. POST /inventory/export/     ← NUEVO
   → Toma los devices del canvas y crea registros cameras / other_devices
   → Asociados a installation_id
   → Idempotente: re-llamar solo crea los devices nuevos
        ↓
3. Vista interna de revisión (panel de administración)
   → Se revisan los datos del project_site
   → Se puede rechazar (verification_status: "rejected" + rejection_reason)
        ↓
4. POST /sites/ { project_site_id: <id> }
   → Promueve el project_site a la tabla sites oficial
   → Actualiza la installation para apuntar al site real
   → Registra authorized_by (usuario que aprobó) + authorized_at
   → El sitio ahora sí aparece en el dashboard principal
```

---

## Endpoint 1 — Crear sitio en staging

### `POST /onboarding/`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access_token>   ← si usas JWT
```
o cookie automática con `axios.defaults.withCredentials = true`.

---

### Body

```ts
interface SiteOnboardingPayload {
  // ─── Campos del sitio (se guardan en project_sites) ──────────────
  name: string               // REQUERIDO. Nombre del sitio/cliente.
  customer_group_id: number  // REQUERIDO. ID del grupo de cliente.
  ip_address?: string        // Opcional. IP del sitio. Default: "0.0.0.0"
  address?: string           // Opcional. Dirección física completa.
  city?: string              // Opcional. Ciudad.
  state_code?: string        // Opcional. Código de estado/provincia (ej. "FL", "TX"). MAX 2 chars.
  country_code?: string      // Opcional. Código de país (ej. "US"). MAX 2 chars.
  teams_channelid?: string   // Opcional. ID de canal de Teams.
  teams_teamid?: string      // Opcional. ID de equipo de Teams.
  lat?: number               // Opcional. Latitud del sitio (del canvas sitios[0].lat).
  lng?: number               // Opcional. Longitud del sitio (del canvas sitios[0].lng).

  // ─── Campos de la instalación ─────────────────────────────────────
  it_lead_tech_id: number       // REQUERIDO. ID del técnico líder (tabla users).
  installation_type_id: number  // REQUERIDO. ID del tipo de instalación.
  project_owner?: number        // Opcional. ID del responsable general (tabla users).
  total_cameras?: number        // Opcional. Total de cámaras estimadas. Default: 0
  total_views?: number          // Opcional. Total de vistas estimadas. Default: 0
  total_devices_planned?: number // Opcional. Alias de total_cameras — count total de devices del canvas.
                                 // Si se envía, sobreescribe total_cameras.
  starting_date?: string        // Opcional. ISO 8601. Ej: "2026-06-01T08:00:00"
  limit_date?: string           // Opcional. ISO 8601. Ej: "2026-08-31T18:00:00"
}
```

> `inst_status_id` **no se envía** — el backend lo resuelve automáticamente a `Active`.
> `state_code` y `country_code` tienen **máximo 2 caracteres** — enviar código, no nombre completo.

---

### Ejemplos de request

**Mínimo:**
```json
{
  "name": "AS Courtesy Collision Orlando",
  "customer_group_id": 1,
  "it_lead_tech_id": 6,
  "installation_type_id": 1
}
```

**Completo (con lat/lng y total_devices_planned):**
```json
{
  "name": "AS Courtesy Collision Orlando",
  "customer_group_id": 1,
  "ip_address": "10.10.5.20",
  "address": "305 Crater Lane, Tampa, FL 33619",
  "city": "Tampa",
  "state_code": "FL",
  "country_code": "US",
  "lat": 27.9506,
  "lng": -82.4572,
  "it_lead_tech_id": 6,
  "installation_type_id": 1,
  "project_owner": 12,
  "total_devices_planned": 27,
  "starting_date": "2026-06-01T08:00:00",
  "limit_date": "2026-08-31T18:00:00"
}
```

---

### Response `201 Created`

```ts
interface SiteOnboardingResponse {
  installation_id: number
  site_id: number           // ⚠️ Ahora es el ID del project_site, no de sites
  site_name: string
  status: string            // Siempre "Active" al crear
  project_owner: number | null
  project_owner_name: string | null
  it_lead_tech_id: number | null
  it_lead_tech_name: string | null
  installation_type_id: number
  installation_type: string | null
  total_cameras: number | null
  total_views: number | null
  starting_date: string | null  // ISO 8601
  limit_date: string | null     // ISO 8601
  total_hours: number           // Siempre 0.0 al crear
  created_at: string            // ISO 8601
}
```

---

### Errores posibles

| Código | Cuándo ocurre | `detail` de ejemplo |
|---|---|---|
| `400` | Campo requerido faltante | `{"name": ["This field is required."]}` |
| `400` | `state_code` más de 2 chars | `{"state_code": ["Ensure this field has no more than 2 characters."]}` |
| `400` | Estado "Active" no existe en BD | `{"detail": "Active status not found in inst_statuses"}` |
| `401` | Sin token / cookie expirada | — |
| `500` | FK inválida (ej. `it_lead_tech_id` no existe) | — |

---

## Endpoint 2 — Exportar inventario del canvas (NUEVO)

### `POST /inventory/export/`

Toma el snapshot completo del canvas y crea los registros `cameras` / `other_devices`
en la BD, asociados a la instalación. Es **idempotente**: re-llamar solo crea los devices
nuevos (los que ya existen en `visual_metadata` se omiten automáticamente).

**Cuándo llamarlo:**
- **Flujo 1 (sitio nuevo):** Llamar justo después de `POST /onboarding/`, pasando el `installation_id` que retornó.
- **Flujo 2 (sitio existente / "Update Inventory"):** Llamar directamente con `installation_id` del sitio activo.

---

### Body

```ts
interface InventoryExportPayload {
  installation_id: number           // REQUERIDO. ID de la instalación.
  sitio?: {
    id?: string
    nombre?: string
    lat?: number
    lng?: number
    zoom?: number
  }
  projectName?: string
  devices: DeviceInstance[]         // Devices del canvas (outdoor/general)
  indoorDevices?: IndoorDevice[]    // Devices del canvas (indoor)
  enlaces?: Enlace[]
  drawings?: DrawingItem[]
}

interface DeviceInstance {
  instanceId: string        // ID único en el canvas (usado para dedup)
  catalogoId: string        // ID del modelo (camera_model_id o device_type_id)
  category: string          // "camera" → cameras table; cualquier otro → other_devices
  networkDeviceId?: number  // FK a devices (switch al que se conecta). Opcional para indoor.
}

interface IndoorDevice {
  instanceId: string
  catalogoId: string
  area?: string             // Nombre del área interior (ej. "Lobby")
  category?: string         // Default: "other"
  networkDeviceId?: number
}
```

---

### Response `200 OK`

```ts
interface InventoryExportResponse {
  success: true
  site_id: number
  installation_id: number
  created_cameras: number        // Nuevos registros en cameras
  created_other_devices: number  // Nuevos registros en other_devices
}
```

```json
{
  "success": true,
  "site_id": 377,
  "installation_id": 19,
  "created_cameras": 8,
  "created_other_devices": 3
}
```

---

### Errores posibles

| Código | Cuándo ocurre | `detail` de ejemplo |
|---|---|---|
| `400` | `installation_id` no existe | `{"detail": "Installation 99 not found."}` |
| `401` | Sin token / cookie expirada | — |

---

## Endpoint 3 — Promover project_site a site oficial

### `POST /sites/`

Este endpoint tiene ahora **dos modos de uso** según los campos que se envíen:

---

#### Modo A — Promover desde staging (nuevo)

```json
{ "project_site_id": 42 }
```

**Response `201 Created`:**
```json
{ "site_id": 377 }
```

---

#### Modo B — Crear site directo (comportamiento original)

```ts
interface SiteCreatePayload {
  name: string
  customer_group_id: number
  ip_address?: string
  teams_channelid?: string
  teams_teamid?: string
}
```

**Response:** `{ "site_id": number }`

---

## Flujo de implementación React — Sitio nuevo (Flujo 1)

```tsx
const onSubmitOnboarding = async (formData: OnboardingPayload) => {
  // 1. Crear el sitio en staging
  const { installation_id } = await axios.post(
    '/api/v1/installations/onboarding/',
    {
      ...formData,
      lat: canvasData.sitios[0]?.lat,
      lng: canvasData.sitios[0]?.lng,
      total_devices_planned: canvasData.devices.length + (canvasData.indoorDevices?.length ?? 0),
    },
    { withCredentials: true }
  ).then(r => r.data)

  // 2. Exportar los devices del canvas
  await axios.post(
    '/api/v1/installations/inventory/export/',
    {
      installation_id,
      sitio: canvasData.sitios[0],
      devices: canvasData.devices,
      indoorDevices: canvasData.indoorDevices ?? [],
      enlaces: canvasData.enlaces ?? [],
      drawings: canvasData.drawings ?? [],
    },
    { withCredentials: true }
  )

  // ⚠️ NO redirigir al dashboard de sites — el site todavía no está aprobado
  router.push(`/installations/${installation_id}`)
}
```

---

## Flujo de implementación React — Sitio existente (Flujo 2 — "Update Inventory")

```tsx
const onUpdateInventory = async (installationId: number) => {
  const result = await axios.post(
    '/api/v1/installations/inventory/export/',
    {
      installation_id: installationId,
      devices: canvasData.devices,
      indoorDevices: canvasData.indoorDevices ?? [],
    },
    { withCredentials: true }
  ).then(r => r.data)

  console.log(`Nuevos: ${result.created_cameras} cámaras, ${result.created_other_devices} otros`)
}
```

---

## Campos de verificación y autorización en project_sites

```ts
interface ProjectSiteVerification {
  verification_status: 'pending' | 'verified' | 'rejected'
  verified_by: number | null
  verified_at: string | null
  authorized_by: number | null
  authorized_at: string | null
  rejection_reason: string | null
}
```

| `verification_status` | Badge sugerido | Acción disponible |
|---|---|---|
| `"pending"` | En revisión | — (solo lectura) |
| `"verified"` | Aprobado | — (site ya en producción) |
| `"rejected"` | Rechazado | Mostrar `rejection_reason`, opción de re-enviar |

---

## Catálogos de referencia (sin cambios)

### Tipos de instalación
```
GET /api/v1/installations/catalog/installation-types/
```

### Técnicos / Lead Techs
```
GET /api/v1/installations/users/lead-techs/
```

### Project Owners
```
GET /api/v1/installations/users/project-owners/
```

### Grupos de clientes
```
GET /api/v1/installations/customer-groups/
```

---

## Resumen de cambios por endpoint

| Endpoint | Cambio |
|---|---|
| `POST /onboarding/` | Agrega `lat`, `lng`, `total_devices_planned` al payload |
| `POST /inventory/export/` | **NUEVO** — exporta devices del canvas a la BD |
| `POST /sites/` | Sin cambios de interfaz |
