# Camera Model Catalog API — Guía para Frontend

> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación:** Cookie `sig_token` (HttpOnly, se setea automáticamente en el login)

```ts
axios.defaults.withCredentials = true
```

---

## ¿Para qué sirve este endpoint?

Retorna el **catálogo maestro** de todos los modelos de cámara que la empresa tiene registrados, sin estar atado a ningún sitio ni unidad física.

### Diferencia clave con `GET /sites/<site_id>/catalog/`

| | `GET /catalog/camera-models/` | `GET /sites/<id>/catalog/` |
|---|---|---|
| **Fuente** | Tabla `camera_models` (modelos) | Tabla `cameras` (unidades físicas) |
| **Alcance** | Global — toda la empresa | Por sitio específico |
| **serial** | Siempre `null` | Serial de la unidad física instalada |
| **ip** | Siempre `null` | IP asignada al dispositivo |
| **Uso** | Crear nueva instalación / elegir modelos | Ver qué hay instalado en un sitio |

**Usa este endpoint cuando el usuario está asignando cámaras a una instalación nueva.** Usa el de sitio cuando quieres ver el inventario real de un sitio existente.

---

## Endpoint

### `GET /catalog/camera-models/`

No requiere parámetros.

**Response `200 OK`:**

```json
[
  {
    "id": "cam-168",
    "name": "IP2M-853E",
    "brand": "AMCREST",
    "serial": null,
    "ip": null,
    "resolution": null,
    "type": null,
    "category": "camera",
    "subtype": "bullet",
    "lensType": null,
    "rango_lente_mm": null,
    "rango_fov_grados": null,
    "poe_watts": null,
    "bandwidth_mbps": null
  },
  {
    "id": "cam-1",
    "name": "DS-2CD2T47G2-L",
    "brand": "HIKVISION",
    "serial": null,
    "ip": null,
    "resolution": null,
    "type": null,
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

- Actualmente retorna **218 modelos**.
- Ordenados por `subtype → brand → name`.

---

## Schema del objeto

```ts
// Reutiliza exactamente la misma interface que el catálogo por sitio
export interface CameraModel {
  id: string              // "cam-{camera_models.id}" — identifica el MODELO
  name: string            // Nombre del modelo. Ej: "DS-2CD2T47G2-L"
  brand: string           // Marca en MAYÚSCULAS. Ej: "HIKVISION"
  serial: null            // Siempre null — no es una unidad física
  ip: null                // Siempre null — no tiene dispositivo asignado
  resolution: null        // Pendiente de columna en DB
  type: string | null     // Descripción del tipo. Ej: "Exterior Bullet Camera"
  category: 'camera'      // Siempre "camera"
  subtype: string         // Tipo en minúsculas. Ver tabla de subtypes abajo.
  lensType: null          // Pendiente de columna en DB
  rango_lente_mm: null    // Pendiente de columna en DB
  rango_fov_grados: null  // Pendiente de columna en DB
  poe_watts: null         // Pendiente de columna en DB
  bandwidth_mbps: null    // Pendiente de columna en DB
}
```

> Los campos `null` fijos se poblarán cuando se agreguen las columnas en `camera_models`. **El schema no cambiará** — solo dejarán de ser `null`.

---

## Subtypes disponibles (valores reales de la DB)

| `subtype` | Descripción |
|---|---|
| `"bullet"` | Cámara tipo bullet exterior/interior |
| `"dome"` | Cámara tipo domo |
| `"turret"` | Cámara tipo torreta |
| `"ptz singleview"` | PTZ de vista única |
| `"ptz dualview"` | PTZ con doble lente |
| `"ptz panoview"` | PTZ panorámica |
| `"fisheye"` | Ojo de pez (360°) |
| `"dual dome"` | Domo dual |
| `"exterior bullet"` | Bullet para exteriores específicos |
| `"panoview (single lens)"` | Panorámica — 1 lente |
| `"panoview (three lenses)"` | Panorámica — 3 lentes |
| `"panoview (four lenses)"` | Panorámica — 4 lentes |
| `"doorbell"` | Cámara de timbre/entrada |
| `"pinhole camera"` | Cámara oculta tipo pinhole |
| `"lpr bullet"` | Bullet para lectura de placas (LPR) |
| `"thermal (single lens)"` | Térmica — 1 lente |
| `"thermal (dual lens)"` | Térmica — 2 lentes |

Útil para filtrar por categoría en el formulario de asignación de cámaras.

---

## Implementación en React / Axios

```ts
// api/catalog.ts
import axios from 'axios'
import type { CameraModel } from '@/types/catalog'

const BASE = 'http://192.168.101.135:8000/api/v1/installations'

/** Catálogo maestro — todos los modelos disponibles para asignar */
export async function getCameraModelCatalog(): Promise<CameraModel[]> {
  const { data } = await axios.get<CameraModel[]>(
    `${BASE}/catalog/camera-models/`,
    { withCredentials: true }
  )
  return data
}
```

### Hook React

```tsx
import { useState, useEffect } from 'react'
import { getCameraModelCatalog } from '@/api/catalog'
import type { CameraModel } from '@/types/catalog'

export function useCameraModelCatalog() {
  const [models, setModels] = useState<CameraModel[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    getCameraModelCatalog()
      .then(setModels)
      .finally(() => setLoading(false))
  }, [])

  return { models, loading }
}
```

### Filtrar por subtype en el componente

```tsx
const { models } = useCameraModelCatalog()

// Agrupar por subtype para mostrar secciones
const bySubtype = models.reduce<Record<string, CameraModel[]>>((acc, m) => {
  ;(acc[m.subtype] ??= []).push(m)
  return acc
}, {})

// Filtrar solo bullets
const bullets = models.filter(m => m.subtype === 'bullet')

// Agrupar por brand para mostrar marca
const byBrand = models.reduce<Record<string, CameraModel[]>>((acc, m) => {
  ;(acc[m.brand] ??= []).push(m)
  return acc
}, {})
```

---

## Flujo de uso en "Crear Nueva Instalación"

```
1. Pantalla "Nueva Instalación" monta el componente
        ↓
2. GET /catalog/camera-models/   ← cargar UNA sola vez, puede cachearse
        ↓
3. Usuario elige modelos del listado y asigna cantidad + IP por unidad
   (la IP se guarda local hasta confirmar, no en este endpoint)
        ↓
4. Al guardar → POST /onboarding/  con los datos del sitio e instalación
        ↓
5. Opcional: POST /projects/<inst_id>/sync/ con las cámaras asignadas
```

> **Tip de performance:** Este catálogo no cambia frecuentemente. Puedes cachearlo en memoria o en `sessionStorage` para evitar re-fetching en cada render.

---

## Errores posibles

| Status | Causa | Acción sugerida |
|---|---|---|
| `403 Forbidden` | Cookie `sig_token` ausente o expirada | Redirigir al login |
| `500 Internal Server Error` | Error interno del servidor | Mostrar error genérico |

---

## Comparación rápida de endpoints de cámaras

| Endpoint | Cuándo usarlo |
|---|---|
| `GET /catalog/camera-models/` | Formulario de nueva instalación — elegir modelos a instalar |
| `GET /sites/<id>/catalog/` | Ver cámaras físicas ya instaladas en un sitio (con serial e IP) |
| `GET /catalog/cameras/` | Selector jerárquico (Type → Brand → Model) para formularios anidados |
