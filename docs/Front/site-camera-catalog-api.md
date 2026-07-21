# Site Device Catalog API — Guía para Frontend

> **Base URL:** `http://192.168.101.135:8000/api/v1/installations`  
> **Autenticación:** Cookie `sig_token` (HttpOnly, se setea automáticamente en el login)

```ts
// Requerido en todas las llamadas
axios.defaults.withCredentials = true
```

Si la cookie no está presente o expiró → `403 Forbidden`.

---

## Endpoint unificado

### `GET /sites/<site_id>/catalog/`

Retorna **todos los dispositivos instalados en un sitio** en una única lista plana.  
Reemplaza los dos endpoints anteriores (`/catalog/` solo cámaras y `/catalog/switches/`).

| Tipo de dispositivo | `category`  | `subtype`          | Prefijo de `id` |
|---------------------|-------------|--------------------|-----------------|
| Cámara (bullet, dome, ptz, …) | `"camera"`  | `camera_types.name` | `cam-`     |
| Switch              | `"network"` | `"switch"`         | `switch-`       |
| Router              | `"network"` | `"router"`         | `router-`       |
| PDU                 | `"power"`   | `"pdu"`            | `pdu-`          |
| DA                  | `"video"`   | `"da"`             | `da-`           |
| Radio               | `"wireless"`| `"radio"`          | `radio-`        |
| Access Control      | `"security"`| `"access_control"` | `ac-`           |

**URL params:**

| Param | Tipo | Descripción |
|---|---|---|
| `site_id` | integer | ID numérico del sitio |

**Response `200 OK`:**

```json
[
  {
    "id": "cam-9753",
    "name": "IP3M-954E",
    "brand": "AMCREST",
    "serial": "2G01234567",
    "ip": "192.168.5.106",
    "resolution": null,
    "type": null,
    "category": "camera",
    "subtype": "bullet",
    "lensType": "varifocal",
    "rango_lente_mm": [2.8, 12],
    "rango_fov_grados": [104, 29],
    "poe_watts": 8,
    "bandwidth_mbps": 5,
    "poe_budget_watts": null,
    "uplink_mbps": null
  },
  {
    "id": "switch-12",
    "name": "SG350-10",
    "brand": "Cisco",
    "serial": "FOC2034X1AB",
    "ip": "192.168.1.2",
    "resolution": null,
    "type": null,
    "category": "network",
    "subtype": "switch",
    "lensType": null,
    "rango_lente_mm": null,
    "rango_fov_grados": null,
    "poe_watts": null,
    "bandwidth_mbps": null,
    "poe_budget_watts": null,
    "uplink_mbps": null
  },
  {
    "id": "router-7",
    "name": "RV345P",
    "brand": "Cisco",
    "serial": "FTX2244B0GZ",
    "ip": "192.168.1.1",
    "resolution": null,
    "type": null,
    "category": "network",
    "subtype": "router",
    "lensType": null,
    "rango_lente_mm": null,
    "rango_fov_grados": null,
    "poe_watts": null,
    "bandwidth_mbps": null,
    "poe_budget_watts": null,
    "uplink_mbps": null
  },
  {
    "id": "pdu-3",
    "name": "AP7930",
    "brand": "Apc",
    "serial": null,
    "ip": null,
    "resolution": null,
    "type": null,
    "category": "power",
    "subtype": "pdu",
    "lensType": null,
    "rango_lente_mm": null,
    "rango_fov_grados": null,
    "poe_watts": null,
    "bandwidth_mbps": null,
    "poe_budget_watts": null,
    "uplink_mbps": null
  },
  {
    "id": "ac-21",
    "name": "HID Edge EVO",
    "brand": "Hid",
    "serial": null,
    "ip": null,
    "resolution": null,
    "type": null,
    "category": "security",
    "subtype": "access_control",
    "lensType": null,
    "rango_lente_mm": null,
    "rango_fov_grados": null,
    "poe_watts": null,
    "bandwidth_mbps": null,
    "poe_budget_watts": null,
    "uplink_mbps": null
  }
]
```

Sitio sin dispositivos → `[]` con status `200`.

---

## Schema del objeto dispositivo

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` | ID único con prefijo según tipo. Ej: `"cam-7"`, `"switch-12"`, `"router-7"`, `"pdu-3"`, `"da-5"`, `"radio-9"`, `"ac-21"` |
| `name` | `string` | Nombre/modelo del dispositivo |
| `brand` | `string` | Marca. Cámaras en MAYÚSCULAS, otros devices en Title Case |
| `serial` | `string | null` | Número de serie físico. `null` si no fue registrado |
| `ip` | `string | null` | IP de red desde tabla `devices`. `null` si no tiene dispositivo asociado |
| `resolution` | `null` | Reservado. Siempre `null` por ahora |
| `type` | `string | null` | Para cámaras: `camera_types.description`. Para otros: `null` |
| `category` | `string` | Agrupación lógica: `"camera"`, `"network"`, `"power"`, `"video"`, `"wireless"`, `"security"` |
| `subtype` | `string` | Tipo específico: `"bullet"`, `"dome"`, `"ptz"`, `"switch"`, `"router"`, `"pdu"`, `"da"`, `"radio"`, `"access_control"` |
| `lensType` | `string \| null` | Solo cámaras: `fixed`\|`varifocal`\|`hybrid`, real (si se cargó el spec de fábrica en el admin) o default por *subtype*. `null` para dispositivos que no son cámara |
| `rango_lente_mm` | `[number, number] \| null` | Solo cámaras: `[min, max]` mm, real o default por *subtype*. `null` para no-cámaras |
| `rango_fov_grados` | `[number, number] \| null` | Solo cámaras: `[min, max]` grados, real o default por *subtype*. `null` para no-cámaras |
| `poe_watts` | `number \| null` | Solo cámaras: real o default por *subtype*. `null` para no-cámaras |
| `bandwidth_mbps` | `number \| null` | Solo cámaras: real o default por *subtype*. `null` para no-cámaras |
| `poe_budget_watts` | `null` | Reservado (dispositivos de red). Siempre `null` por ahora |
| `uplink_mbps` | `null` | Reservado (dispositivos de red). Siempre `null` por ahora |

> `lensType`/`rango_lente_mm`/`rango_fov_grados`/`poe_watts`/`bandwidth_mbps` ahora vienen de columnas reales
> en `camera_models` (ver `docs/db/camera_models_schema.md`), cargadas manualmente vía el admin de Django.
> Si el modelo de la cámara instalada tiene su spec de fábrica cargado, se devuelve ese valor; si no, el
> mismo default genérico por *subtype* que ya se devolvía antes para el catálogo general. Antes este
> endpoint (`/sites/<id>/catalog/`) sí devolvía estos campos siempre en `null` para cámaras — eso cambió.
> `poe_budget_watts`/`uplink_mbps` siguen reservados (son specs de dispositivos de red, no de cámaras). El
> shape no cambió.

---

## TypeScript

```ts
// types/catalog.ts
export interface SiteDeviceItem {
  id: string
  name: string
  brand: string
  serial: string | null
  ip: string | null
  resolution: string | null
  type: string | null
  category: string
  subtype: string
  lensType: string | null
  rango_lente_mm: number[] | null
  rango_fov_grados: number[] | null
  poe_watts: number | null
  bandwidth_mbps: number | null
  poe_budget_watts: number | null
  uplink_mbps: number | null
}

// Subtypes de categoría para narrowing
export type CameraSubtype =
  | 'bullet' | 'dome' | 'ptz' | 'fisheye'
  | 'ptz dualview' | 'ptz panoview' | 'ptz singleview'
  | 'dual dome' | 'panoview (four lenses)'
  | 'thermal (dual lens)' | 'thermal (single lens)'
  | 'turret' | 'box' | 'mini dome' | 'license plate'

export type NetworkSubtype = 'switch' | 'router'
export type PowerSubtype = 'pdu'
export type VideoSubtype = 'da'
export type WirelessSubtype = 'radio'
export type SecuritySubtype = 'access_control'

// Type guards
export const isCamera = (d: SiteDeviceItem): boolean => d.category === 'camera'
export const isSwitch = (d: SiteDeviceItem): boolean => d.subtype === 'switch'
export const isRouter = (d: SiteDeviceItem): boolean => d.subtype === 'router'
```

---

## Uso — React hook

```ts
// api/catalog.ts
import axios from 'axios'
import type { SiteDeviceItem } from '@/types/catalog'

const BASE = 'http://192.168.101.135:8000/api/v1/installations'

export async function getSiteDeviceCatalog(siteId: number): Promise<SiteDeviceItem[]> {
  const { data } = await axios.get<SiteDeviceItem[]>(
    `${BASE}/sites/${siteId}/catalog/`,
    { withCredentials: true }
  )
  return data
}
```

```tsx
// hooks/useSiteDeviceCatalog.ts
import { useState, useEffect } from 'react'
import { getSiteDeviceCatalog } from '@/api/catalog'
import type { SiteDeviceItem } from '@/types/catalog'

export function useSiteDeviceCatalog(siteId: number) {
  const [devices, setDevices] = useState<SiteDeviceItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!siteId) return
    setLoading(true)
    getSiteDeviceCatalog(siteId)
      .then(setDevices)
      .finally(() => setLoading(false))
  }, [siteId])

  // Helpers de filtrado
  const cameras = devices.filter(d => d.category === 'camera')
  const switches = devices.filter(d => d.subtype === 'switch')
  const routers = devices.filter(d => d.subtype === 'router')
  const pdus = devices.filter(d => d.subtype === 'pdu')
  const das = devices.filter(d => d.subtype === 'da')
  const radios = devices.filter(d => d.subtype === 'radio')
  const accessControls = devices.filter(d => d.subtype === 'access_control')

  return { devices, cameras, switches, routers, pdus, das, radios, accessControls, loading }
}
```

```tsx
// Ejemplo de uso en componente
function SiteDeviceList({ siteId }: { siteId: number }) {
  const { cameras, switches, routers, loading } = useSiteDeviceCatalog(siteId)

  if (loading) return <Spinner />

  return (
    <div>
      <section>
        <h2>Cámaras ({cameras.length})</h2>
        {cameras.map(cam => (
          <DeviceCard key={cam.id} device={cam} />
        ))}
      </section>
      <section>
        <h2>Switches ({switches.length})</h2>
        {switches.map(sw => (
          <DeviceCard key={sw.id} device={sw} />
        ))}
      </section>
      <section>
        <h2>Routers ({routers.length})</h2>
        {routers.map(r => (
          <DeviceCard key={r.id} device={r} />
        ))}
      </section>
    </div>
  )
}
```

---

## Filtrado y agrupación

```ts
// Filtrar por cualquier tipo
const byCategory = (cat: string) => devices.filter(d => d.category === cat)
const bySubtype = (sub: string) => devices.filter(d => d.subtype === sub)

// Agrupar por categoría
const grouped = devices.reduce((acc, d) => {
  ;(acc[d.category] ??= []).push(d)
  return acc
}, {} as Record<string, SiteDeviceItem[]>)

// Agrupar por subtype (para mostrar chips/badges)
const subtypeCounts = devices.reduce((acc, d) => {
  acc[d.subtype] = (acc[d.subtype] ?? 0) + 1
  return acc
}, {} as Record<string, number>)
// Ej: { bullet: 6, dome: 2, switch: 2, router: 1, pdu: 1 }
```

---

## Migración desde los endpoints anteriores

| Antes | Ahora |
|---|---|
| `GET /sites/<id>/catalog/` (solo cámaras) | `GET /sites/<id>/catalog/` (todos los dispositivos) |
| `GET /sites/<id>/catalog/switches/` | Eliminado — incluido en el endpoint unificado |

**Cambios de schema:**
- Las cámaras ahora incluyen `poe_budget_watts` y `uplink_mbps` (siempre `null`)
- Los switches cambian: `category` era `"static"`, ahora es `"network"`; `resolution` era `"—"`, ahora es `null`
- Los otros dispositivos son nuevos: `router`, `pdu`, `da`, `radio`, `access_control`

---

## Endpoint de Sitios

### `GET /sites/`

Lista todos los sitios activos. Incluye `customer_group_id` para filtrar por grupo, además de `address`, `status`, `responsable` e `it_manager`.

**Response `200 OK`:**

```json
[
  {
    "id": 305,
    "name": "AS 3281 Storage Lot",
    "customer_group_id": 2,
    "location": "Dallas, TX",
    "address": "3281 Manor Way, Dallas, TX 75235",
    "status": "Active",
    "responsable": "John Doe",
    "it_manager": "Jane Smith",
    "notes": null,
    "log": []
  }
]
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `number` | ID del sitio — usar como `site_id` en `/catalog/` |
| `name` | `string` | Nombre del sitio |
| `customer_group_id` | `number` | ID del grupo cliente — usar para filtrar sitios por grupo |
| `location` | `string | null` | Ciudad y estado (`"Dallas, TX"`). `null` si no tiene ninguno |
| `address` | `string | null` | Dirección física. Puede contener `

` — limpiar antes de mostrar |
| `status` | `string | null` | Estado de la instalación más reciente |
| `responsable` | `string | null` | Project owner de la instalación |
| `it_manager` | `string | null` | Responsable IT del sitio |
| `notes` | `string | null` | Nota más reciente |
| `log` | `array` | Historial de notas `[{date, action, user}]` |

---

## Errores posibles

| Status | Causa | Acción sugerida |
|---|---|---|
| `403 Forbidden` | Cookie `sig_token` ausente o expirada | Redirigir al login |
| `404 Not Found` | URL incorrecta | Verificar URL |
| `500 Internal Server Error` | Error interno | Mostrar error genérico |

---

## Notas

- **Cámaras**: una entrada por unidad física (50 cámaras del mismo modelo = 50 entradas)
- **Otros dispositivos**: una entrada por unidad física (`other_devices.id` como ID base)
- Orden: cámaras primero (subtype → brand → name), luego otros dispositivos (device_type → brand → model)
- El `id` es único globalmente dentro de la respuesta (distintos prefijos garantizan no colisión)
