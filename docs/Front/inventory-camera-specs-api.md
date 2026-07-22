# Inventory — Camera Specs API (Frontend Guide)

> **Base URL:** usa el mismo `apiClient`/instancia de axios ya configurada para el resto de llamadas de
> `inventory` (ej. `GET /inventory/articles/`) — **no** una base URL nueva ni un puerto distinto.
> **Autenticación:** Cookie `sig_token` (HttpOnly, se setea automáticamente en el login)

> ⚠️ **El backend nunca expone el puerto 8000 directamente** — `docker/docker-compose.yml` lo declara con
> `expose:` (solo visible entre contenedores), no con `ports:`. Todo el tráfico externo pasa por nginx en
> `:80`/`:443`, que hace proxy interno de `/api/` hacia `web:8000` (`docker/nginx.conf`). Cualquier llamada a
> `http://<host>:8000/...` desde el navegador da `net::ERR_CONNECTION_REFUSED` — y si la página está en
> `https://`, además se bloquea antes por *Mixed Content*. Usa siempre el mismo host/esquema que ya usan las
> demás llamadas de la app (sin `:8000`), no un endpoint nuevo con su propia base URL.

```ts
// Requerido en todas las llamadas
axios.defaults.withCredentials = true
```

Si la cookie no está presente o expiró → `401`/`403`.

---

## ¿Para qué sirve este endpoint?

Permite que un usuario logueado en el módulo de **Inventory** cargue el **spec de fábrica** (rango de lente
y campo de visión) de un modelo de cámara — el mismo dato que ya se ve, cuando existe, en
`GET /catalog/camera-models/` (documentado en `camera-model-catalog-api.md`) y en el catálogo por-sitio
(`site-camera-catalog-api.md`). Es una actualización, no una creación: el modelo de cámara ya existe en el
catálogo, este endpoint solo completa dos de sus campos.

**Por ahora solo escribe `rango_lente_mm` y `rango_fov_grados`.** `poe_watts`, `bandwidth_mbps` y `lensType`
quedan para una integración posterior — no los envíes, el backend los ignora si vienen en el body.

---

## Endpoint

### `POST /camera-specs/`

**Request body:**

```json
{
  "camera_model_id": 168,
  "rango_lente_mm": [2.8, 12],
  "rango_fov_grados": [104, 29]
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `camera_model_id` | integer | **Sí** | El id real del modelo de cámara. Es el mismo número que viene después de `"cam-"` en el `id` que devuelve `GET /catalog/camera-models/` (ej. `"cam-168"` → `168`). |
| `rango_lente_mm` | `[number, number]` | **Sí** | `[min, max]` en milímetros de distancia focal. Exactamente 2 valores, entre 0 y 1000. |
| `rango_fov_grados` | `[number, number]` | **Sí** | `[min, max]` en grados de campo de visión. Exactamente 2 valores, entre 0 y 360. |

**Response `200 OK`:**

```json
{
  "camera_model_id": 168,
  "name": "IP2M-853E",
  "brand": "AMCREST",
  "rango_lente_mm": [2.8, 12],
  "rango_fov_grados": [104, 29]
}
```

> Es un `200`, no un `201` — el modelo de cámara ya existía, esto actualiza dos de sus campos, no crea nada
> nuevo.

**Errores:**

| Status | Causa | Qué mostrar |
|---|---|---|
| `400 Bad Request` | Falta `camera_model_id`, un rango no trae exactamente 2 números, hay un valor negativo, fuera de rango físico (lente > 1000mm, FOV > 360°), o no numérico | El body trae `{campo: [mensaje de error]}` por cada campo inválido — mostrar el mensaje tal cual devuelve DRF |
| `404 Not Found` | El `camera_model_id` no existe en el catálogo | "Modelo de cámara no encontrado" — probablemente un id mal armado, revisar de dónde salió |
| `401` / `403` | Cookie `sig_token` ausente o expirada | Redirigir al login |

---

## Patrón en el frontend

```ts
// api/cameraSpecs.ts
// Reusa el mismo cliente/instancia de axios que ya usa el resto de inventory
// (el que hace funcionar GET /inventory/articles/, etc.) — NO crear una base
// URL nueva ni apuntar a un puerto distinto (ver advertencia arriba).
import { apiClient } from './apiClient'   // ajustar al import real del proyecto

export interface CameraSpecUpdatePayload {
  camera_model_id: number
  rango_lente_mm: [number, number]
  rango_fov_grados: [number, number]
}

export interface CameraSpec {
  camera_model_id: number
  name: string
  brand: string | null
  rango_lente_mm: [number, number]
  rango_fov_grados: [number, number]
}

export async function updateCameraSpec(payload: CameraSpecUpdatePayload): Promise<CameraSpec> {
  // Ruta relativa — apiClient ya trae configurado el host/esquema correcto (vía nginx)
  const { data } = await apiClient.post<CameraSpec>('/inventory/camera-specs/', payload)
  return data
}
```

```tsx
// Ejemplo de uso en un formulario
async function handleSubmit(modelId: number, lenteMin: number, lenteMax: number, fovMin: number, fovMax: number) {
  try {
    const spec = await updateCameraSpec({
      camera_model_id: modelId,
      rango_lente_mm: [lenteMin, lenteMax],
      rango_fov_grados: [fovMin, fovMax],
    })
    toast.success(`Spec de ${spec.name} actualizado`)
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 400) {
      // err.response.data trae { camera_model_id: [...], rango_lente_mm: [...], ... }
      showFieldErrors(err.response.data)
    } else if (axios.isAxiosError(err) && err.response?.status === 404) {
      toast.error('Modelo de cámara no encontrado')
    } else {
      toast.error('Error inesperado al guardar el spec')
    }
  }
}
```

---

## De dónde sacar el `camera_model_id`

El formulario necesita listar los modelos de cámara disponibles para que el usuario elija uno. Usa el
catálogo maestro que ya existe:

```ts
// GET /api/v1/installations/catalog/camera-models/  (documentado en camera-model-catalog-api.md)
const models = await getCameraModelCatalog()
// cada item trae "id": "cam-168" — quita el prefijo "cam-" para obtener camera_model_id: 168
const cameraModelId = Number(model.id.replace('cam-', ''))
```

Ese mismo catálogo ya trae `rango_lente_mm`/`rango_fov_grados` — si el modelo elegido ya tiene un spec real
cargado (no el default genérico), tiene sentido pre-llenar el formulario con esos valores en vez de dejarlo
vacío, para que el usuario solo edite lo que quiere cambiar.

---

## Qué NO hace este endpoint

- No crea modelos de cámara nuevos — `camera_model_id` debe existir de antes.
- No toca `poe_watts`, `bandwidth_mbps` ni `lensType` — quedan en lo que tuvieran antes.
- No es batch — un modelo por request. Si necesitas cargar varios, son varios `POST` secuenciales.
- El cambio se refleja **de inmediato** en `GET /catalog/camera-models/` (sin esperar caché) — no hace falta
  ningún refresh especial del lado del frontend más allá de volver a pedir el catálogo si lo tenías guardado
  en estado local.
