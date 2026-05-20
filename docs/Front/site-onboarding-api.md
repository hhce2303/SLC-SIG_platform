# Site Onboarding API — Guía para el Frontend

> **Endpoint:** `POST /api/v1/installations/onboarding/`  
> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación:** Cookie `sig_token` (HttpOnly) o Bearer Token JWT

```ts
// Requerido en todas las llamadas
axios.defaults.withCredentials = true
```

---

## ¿Para qué sirve este endpoint?

Crea un **sitio** y su **primera instalación** en una sola operación atómica (transacción).  
Si cualquiera de los dos inserts falla, **ninguno** se guarda en la base de datos.

El endpoint retorna el registro completo de la instalación creada, listo para usarse en el flujo post-creación (redirigir al dashboard de la instalación, pre-cargar el formulario, etc.).

---

## Request

### `POST /onboarding/`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access_token>   ← si usas JWT
```
o si usas cookie (recomendado): `axios.defaults.withCredentials = true` y nada más.

---

### Body — Campos disponibles

```ts
interface SiteOnboardingPayload {
  // ─── Campos del sitio ────────────────────────────────────────────
  name: string               // REQUERIDO. Nombre del sitio/cliente.
  customer_group_id: number  // REQUERIDO. ID del grupo de cliente.
  ip_address?: string        // Opcional. IP del sitio. Default: "0.0.0.0"
  address?: string           // Opcional. Dirección física completa.
  city?: string              // Opcional. Ciudad.
  state_code?: string        // Opcional. Código de estado/provincia (ej. "FL", "TX").
  country_code?: string      // Opcional. Código de país (ej. "US").
  teams_channelid?: string   // Opcional. ID de canal de Teams.
  teams_teamid?: string      // Opcional. ID de equipo de Teams.

  // ─── Campos de la instalación ────────────────────────────────────
  it_lead_tech_id: number          // REQUERIDO. ID del técnico líder (tabla users).
  installation_type_id: number     // REQUERIDO. ID del tipo de instalación (ver tabla abajo).
  project_owner?: number           // Opcional. ID del responsable general (tabla users).
  total_cameras?: number           // Opcional. Total de cámaras estimadas. Default: 0
  total_views?: number             // Opcional. Total de vistas estimadas. Default: 0
  starting_date?: string           // Opcional. ISO 8601. Ej: "2026-06-01T08:00:00"
  limit_date?: string              // Opcional. ISO 8601. Ej: "2026-08-31T18:00:00"
}
```

> **Nota:** `inst_status_id` **no se envía** — el backend lo resuelve automáticamente a `Active`.

---

### Ejemplo mínimo

```json
{
  "name": "AS Courtesy Collision Orlando",
  "customer_group_id": 1,
  "it_lead_tech_id": 6,
  "installation_type_id": 1
}
```

### Ejemplo completo

```json
{
  "name": "AS Courtesy Collision Orlando",
  "customer_group_id": 1,
  "ip_address": "10.10.5.20",
  "address": "305 Crater Lane, Tampa, FL 33619",
  "city": "Tampa",
  "state_code": "FL",
  "country_code": "US",
  "it_lead_tech_id": 6,
  "installation_type_id": 1,
  "project_owner": 12,
  "total_cameras": 24,
  "total_views": 4,
  "starting_date": "2026-06-01T08:00:00",
  "limit_date": "2026-08-31T18:00:00"
}
```

---

## Response

### `201 Created`

```ts
interface SiteOnboardingResponse {
  installation_id: number
  site_id: number
  site_name: string
  status: string               // Siempre "Active" al crear
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

```json
{
  "installation_id": 215,
  "site_id": 377,
  "site_name": "AS Courtesy Collision Orlando",
  "status": "Active",
  "project_owner": 12,
  "project_owner_name": "Brian Lozada",
  "it_lead_tech_id": 6,
  "it_lead_tech_name": "Jose Velasquez",
  "installation_type_id": 1,
  "installation_type": "Primary",
  "total_cameras": 24,
  "total_views": 4,
  "starting_date": "2026-06-01T08:00:00",
  "limit_date": "2026-08-31T18:00:00",
  "total_hours": 0.0,
  "created_at": "2026-05-19T03:25:41"
}
```

---

### Errores posibles

| Código | Cuándo ocurre | `detail` de ejemplo |
|---|---|---|
| `400 Bad Request` | Campo requerido faltante o inválido | `{"name": ["This field is required."]}` |
| `400 Bad Request` | El estado "Active" no existe en BD | `{"detail": "Active status not found in inst_statuses"}` |
| `401 Unauthorized` | Sin token / cookie expirada | — |
| `500 Internal Server Error` | FK inválida (ej. `it_lead_tech_id` no existe) | — |

---

## Catálogos de referencia (IDs)

Antes de hacer el POST, el frontend debe obtener los IDs válidos desde estos endpoints:

### Tipos de instalación

```
GET /api/v1/installations/catalog/installation-types/
```

```json
[
  { "id": 1, "name": "Primary" },
  { "id": 2, "name": "Primary existing" },
  { "id": 3, "name": "Maintenance" }
]
```

### Técnicos / Lead Techs

```
GET /api/v1/installations/users/lead-techs/
```

```json
[
  { "id": 6,  "username": "jvelasquez", "name": "Jose Velasquez",  "role": "it-tech" },
  { "id": 12, "username": "blozada",   "name": "Brian Lozada",    "role": "it-tech" }
]
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

## Implementación en React / Axios

```tsx
import axios from 'axios'

interface OnboardingPayload {
  name: string
  customer_group_id: number
  it_lead_tech_id: number
  installation_type_id: number
  address?: string
  city?: string
  state_code?: string
  country_code?: string
  ip_address?: string
  project_owner?: number
  total_cameras?: number
  total_views?: number
  starting_date?: string
  limit_date?: string
}

export async function createSiteWithInstallation(payload: OnboardingPayload) {
  const { data } = await axios.post(
    '/api/v1/installations/onboarding/',
    payload,
    { withCredentials: true }
  )
  return data // SiteOnboardingResponse
}
```

### Uso en un componente con React Hook Form

```tsx
const onSubmit = async (formData: OnboardingPayload) => {
  try {
    const installation = await createSiteWithInstallation(formData)
    // Redirigir al dashboard de la nueva instalación
    router.push(`/installations/${installation.installation_id}`)
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 400) {
      // Mostrar errores de validación
      console.error(err.response.data)
    }
  }
}
```

---

## Flujo completo de pantallas (sugerido)

```
1. Usuario llena el formulario "Nuevo Sitio"
       ↓
2. Frontend carga los catálogos en paralelo:
   - GET /catalog/installation-types/
   - GET /users/lead-techs/
   - GET /users/project-owners/
   - GET /customer-groups/
       ↓
3. Usuario completa y envía el formulario
       ↓
4. POST /onboarding/  →  201 Created
       ↓
5. Usar installation_id y site_id del response para:
   - Redirigir a la vista de detalle de la instalación
   - Pre-cargar el mapa con address/city/state_code
   - Mostrar estado "Active" en el dashboard principal
```

---

## Notas de integración

- El **`status`** en la respuesta siempre será `"Active"` al crear. Esto significa que el sitio aparecerá en el **dashboard verde** (Active Sites) inmediatamente.
- Si `project_owner` no se envía, el campo llega como `null` y el frontend mostrará `"No asignado"`.
- El campo `total_hours` siempre comienza en `0.0` y lo actualiza el sistema de instalación.
- Los campos `starting_date` y `limit_date` aceptan cualquier formato ISO 8601 válido.
