# Guía de migración — specs de fábrica de cámaras ahora vienen de la DB

> Instructivo de **qué cambió** para que el frontend prepare sus ajustes. Para el shape completo de cada
> endpoint, ver `camera-model-catalog-api.md` / `site-camera-catalog-api.md` / `installations-api-reference.md`.

## TL;DR

**No hay breaking change de shape.** Los campos `lensType`, `rango_lente_mm`, `rango_fov_grados`,
`poe_watts` y `bandwidth_mbps` siguen exactamente con los mismos nombres y tipos. Lo que cambia son los
**valores**: ahora pueden venir de la ficha técnica real del modelo de cámara (cargada a mano en un admin),
en vez de ser siempre `null` o siempre un default genérico.

---

## Endpoints afectados

Solo estos dos están realmente activos y afectados:

| Endpoint | Vista | Qué devuelve |
|---|---|---|
| `GET /catalog/camera-models/` | `CameraModelCatalogView` | Catálogo maestro de modelos de cámara (sin sitio) |
| `GET /sites/<site_id>/catalog/` | `SiteDeviceCatalogView` | Catálogo unificado de un sitio — cámaras + switches + otros dispositivos en una sola lista |

> ⚠️ **`installations-api-reference.md` tiene una sección desactualizada.** Su índice describe
> `GET /sites/<site_id>/catalog/` como si devolviera "solo cámaras" y menciona
> `GET /sites/<site_id>/catalog/switches/`. Ninguna de las dos afirmaciones es cierta hoy: la ruta
> `/sites/<site_id>/catalog/` es la **unificada** (cámaras + red juntas), y `/catalog/switches/` **no existe**
> como ruta registrada — las vistas viejas (`SiteCameraCatalogView`/`SiteSwitchCatalogView`) están definidas
> en el código pero no enrutadas. Ignora esa sección del doc de referencia; usa `site-camera-catalog-api.md`
> como fuente de verdad para el catálogo por-sitio.

---

## Qué cambió, antes/después

| Campo | Antes | Ahora |
|---|---|---|
| `lensType` | Catálogo general: default por *subtype* (ej. `"varifocal"`). Catálogo por-sitio: siempre `null`. | Valor real de fábrica si el modelo lo tiene cargado; si no, el mismo default por *subtype* de antes — **en ambos endpoints**. |
| `rango_lente_mm` | Ídem — `[2.8, 12]` genérico o `null` según el endpoint. | Ídem — real o default, nunca más forzado a `null` para cámaras. |
| `rango_fov_grados` | Ídem. | Ídem. |
| `poe_watts` | Ídem. | Ídem. |
| `bandwidth_mbps` | Ídem. | Ídem. |

El cambio real es que el **catálogo por-sitio** (`/sites/<site_id>/catalog/`) dejó de forzar estos 5 campos
a `null` para cámaras — ahora se comporta igual que el catálogo general, que ya tenía el fallback por
*subtype*.

### Ejemplo

```json
// Antes (cámara en /sites/<id>/catalog/)
{
  "id": "cam-9753",
  "subtype": "bullet",
  "lensType": null,
  "rango_lente_mm": null,
  "rango_fov_grados": null,
  "poe_watts": null,
  "bandwidth_mbps": null
}

// Ahora (mismo modelo, sin spec de fábrica cargado todavía → default por subtype)
{
  "id": "cam-9753",
  "subtype": "bullet",
  "lensType": "varifocal",
  "rango_lente_mm": [2.8, 12],
  "rango_fov_grados": [104, 29],
  "poe_watts": 8,
  "bandwidth_mbps": 5
}

// Ahora (mismo modelo, CON spec de fábrica real cargado en el admin)
{
  "id": "cam-9753",
  "subtype": "bullet",
  "lensType": "varifocal",
  "rango_lente_mm": [2.8, 13.5],
  "rango_fov_grados": [98, 27],
  "poe_watts": 7.5,
  "bandwidth_mbps": 4
}
```

Desde el punto de vista del frontend, los tres casos tienen **el mismo shape** — no hay forma de distinguir
"default genérico" de "spec real" por el JSON solo (ambos son datos válidos para mostrar).

---

## Qué debe revisar el frontend

1. **Tipos TypeScript**: si `rango_lente_mm`/`rango_fov_grados` estaban tipados como `null` literal (porque
   nunca traían otra cosa), actualizar a `[number, number] | null`. Mismo para `lensType: string | null`,
   `poe_watts`/`bandwidth_mbps: number | null`.
2. **Lógica condicional en UI**: si había código tipo `if (item.rango_lente_mm === null) mostrar "N/A"`
   específicamente para el catálogo por-sitio, revisarlo — ahora esa rama casi nunca se va a ejecutar (solo
   quedaría `null` para dispositivos que no son cámara, ej. switches/routers, donde ya era `null` y sigue
   siéndolo). No es un error si no lo tocan, pero puede estar ocultando información que ya está disponible.
3. **Nada más cambia**: mismos endpoints, mismos parámetros, misma autenticación (cookie `sig_token` /
   JWT). No hay nuevos endpoints que consumir ni parámetros nuevos que enviar.

---

## Cómo se puebla el dato real

Los valores de fábrica se cargan **a mano**, por ahora, desde el admin de Django (`CameraModelAdmin` en
`apps/sigtools/admin.py`) — todavía no hay importación masiva desde una hoja de cálculo. Esto significa que
la migración es gradual: modelos sin spec cargado seguirán mostrando el default genérico por *subtype*
indefinidamente hasta que alguien complete su ficha técnica. El frontend no necesita hacer nada para que
esto se refleje — es transparente, mismo endpoint, mismo shape.

Detalle de columnas y dónde viven: `docs/db/camera_models_schema.md`.
