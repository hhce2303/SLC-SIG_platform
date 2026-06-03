# SIGplatform — Guía de Integración Frontend

## Entorno de Producción

| Item | Valor |
|---|---|
| **Servidor** | MKS Server |
| **IP del servidor** | `192.168.1.69` |
| **API Base URL** | `http://192.168.1.69/api/v1/` |
| **Puerto expuesto** | `80` (nginx) |
| **Protocolo** | HTTP (LAN interna) |

---

## Configuración de la URL base

Define la base URL de la API en tu proyecto frontend según el entorno:

### Vite / React (`.env.production`)
```env
VITE_API_BASE_URL=http://192.168.1.69/api/v1
```

### Next.js (`.env.production`)
```env
NEXT_PUBLIC_API_BASE_URL=http://192.168.1.69/api/v1
```

### Angular (`environment.prod.ts`)
```typescript
export const environment = {
  production: true,
  apiBaseUrl: 'http://192.168.1.69/api/v1',
};
```

---

## Autenticación JWT

Todos los endpoints protegidos requieren un JWT en el header `Authorization`.

### Obtener tokens

```http
POST http://192.168.1.69/api/v1/auth/token/
Content-Type: application/json

{
  "username": "tu_usuario",
  "password": "tu_password"
}
```

**Respuesta:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

### Usar el access token

```http
GET http://192.168.1.69/api/v1/<endpoint>/
Authorization: Bearer eyJ...
```

### Renovar el access token

```http
POST http://192.168.1.69/api/v1/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJ..."
}
```

**Tiempos de vida:**
- Access token: **60 minutos**
- Refresh token: **7 días**

---

## Endpoints Principales

| Módulo | Prefix | Ejemplo |
|---|---|---|
| Auth / Usuarios | `/api/v1/auth/` | `POST /api/v1/auth/token/` |
| Inventario | `/api/v1/inventory/` | `GET /api/v1/inventory/articles/` |
| Instalaciones | `/api/v1/installations/` | `GET /api/v1/installations/` |
| Logs | `/api/v1/logs/` | `GET /api/v1/logs/` |
| Notificaciones | `/api/v1/notifications/` | `GET /api/v1/notifications/` |
| Schedules | `/api/v1/schedules/` | `GET /api/v1/schedules/` |
| Chatbot | `/api/v1/chatbot/` | `POST /api/v1/chatbot/message/` |
| Reportes | `/api/v1/reports/` | `GET /api/v1/reports/` |
| Platform | `/api/v1/platform/` | `GET /api/v1/platform/` |

**Documentación interactiva (Swagger):** `http://192.168.1.69/api/docs/`  
**OpenAPI schema (raw):** `http://192.168.1.69/api/schema/`

---

## Eventos en Tiempo Real (SSE)

El backend expone Server-Sent Events para actualizaciones en tiempo real. nginx está configurado con buffering desactivado para estos endpoints.

```javascript
const evtSource = new EventSource(
  'http://192.168.1.69/api/v1/realtime/events/',
  { withCredentials: false }
);

evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Evento recibido:', data);
};
```

> **Nota:** Los endpoints SSE no necesitan `Authorization` header en el `EventSource` constructor porque los navegadores no lo soportan. Usa un query param token si requieres autenticación en SSE:  
> `GET /api/v1/realtime/events/?token=<access_token>`

---

## CORS

El servidor tiene configurado CORS para aceptar peticiones desde:
- `http://192.168.1.69` (mismo servidor)
- `http://localhost:3000` (dev React/Next)
- `http://localhost:5173` (dev Vite)

Si tu frontend corre en otro origen, contacta al administrador del backend para agregar el origen a `CORS_ALLOWED_ORIGINS`.

---

## Respuestas de la API

### Formato de respuesta estándar (listas paginadas)

```json
{
  "count": 100,
  "next": "http://192.168.1.69/api/v1/<endpoint>/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

### Formato de error

```json
{
  "detail": "No encontrado."
}
```

```json
{
  "field_name": ["Este campo es requerido."]
}
```

### Códigos HTTP usados

| Código | Significado |
|---|---|
| `200` | OK |
| `201` | Creado |
| `400` | Error de validación |
| `401` | No autenticado (token expirado o ausente) |
| `403` | Sin permiso |
| `404` | No encontrado |
| `500` | Error interno del servidor |

---

## Notas de Nombres de Campo

Los campos en las respuestas de la API usan **camelCase**:

```json
{
  "articleId": 1,
  "serialNumber": "SN-001",
  "updatedAt": "2026-06-03T10:00:00Z"
}
```

---

## Verificar que el servidor esté activo

```bash
curl http://192.168.1.69/api/v1/health/
# Respuesta esperada: {"status": "ok"}
```
