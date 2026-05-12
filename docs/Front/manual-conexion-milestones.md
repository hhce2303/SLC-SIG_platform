# Manual de Conexión Frontend ↔ Backend

Guía operativa para conectar clientes web con `daily-log-backend` de forma incremental. Está organizada por milestones para que el equipo pueda integrar primero lo indispensable y después avanzar hacia módulos más completos sin mezclar contratos ya activos con funcionalidades futuras.

## 1. Objetivo

Este manual cubre cuatro etapas:

1. Auth
2. Gestión de eventos
3. Servicios de apoyo
4. WebSockets a futuro

La idea es que el frontend pueda integrarse por capas, validando cada milestone antes de abrir el siguiente.

## 2. Base de conexión

### 2.1 Base URL

- Desarrollo local backend: `http://localhost:8000/api/v1`
- Health check: `GET /api/v1/health/`
- Swagger UI: `http://localhost:8000/api/docs/`
- OpenAPI schema: `http://localhost:8000/api/schema/`

### 2.2 Variable de entorno recomendada para frontend

```env
VITE_API_URL=http://localhost:8000/api/v1
```

### 2.3 Headers base

Públicos:

```http
Content-Type: application/json
```

Autenticados:

```http
Content-Type: application/json
Authorization: Bearer <access_token>
```

### 2.4 Convenciones generales

- Todos los cuerpos son JSON.
- El backend usa JWT con `access` y `refresh`.
- Los endpoints autenticados requieren el `access token` en header `Authorization`.
- Cuando expire el `access`, el frontend debe llamar a `/auth/token/refresh/` o `/platform/auth/token/refresh/` según el flujo usado.
- Para exploración manual o validación funcional, usar Swagger en `/api/docs/`.

---

## 3. Milestone 1 — Auth

Este milestone resuelve login, sesión operativa y perfil del usuario. Aquí existen dos flujos distintos y es importante no mezclarlos.

### 3.1 Flujo A: Auth Daily con estación

Usar este flujo para la app de Daily Log tradicional, donde el usuario trabaja asociado a una estación.

Base path:

```text
/api/v1/auth/
```

Endpoints activos:

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| POST | `/login/` | No | Login operativo con estación |
| POST | `/logout/` | Sí | Cerrar sesión y liberar estación |
| POST | `/token/refresh/` | No | Renovar access token |
| GET | `/me/` | Sí | Obtener perfil y sesión activa |
| PATCH | `/me/status/` | Sí | Actualizar estado de sesión |
| GET | `/stations/available/` | No | Listar estaciones libres |

#### Request de login

```json
{
  "username": "operador1",
  "password": "1234",
  "station_id": 43
}
```

#### Response de login

```json
{
  "access": "jwt-access-token",
  "refresh": "jwt-refresh-token",
  "user": {
    "id": 25,
    "name": "operador1",
    "role": "Operador",
    "role_id": 2
  },
  "session_id": 912,
  "station_id": 43
}
```

#### Notas operativas

- `station_id` es obligatorio en este flujo.
- Si el usuario ya tiene una sesión activa, el backend responde con conflicto.
- Si la estación ya está ocupada, el backend responde con conflicto.
- `logout` además de cerrar sesión intenta liberar la estación ocupada por el usuario.
- `me` devuelve la sesión activa, incluyendo `station_number` y `sesion_status`.

#### Request de logout

```json
{
  "refresh": "jwt-refresh-token"
}
```

El campo `refresh` es opcional, pero conviene enviarlo para que el backend lo blacklistée cuando corresponda.

#### Request para actualizar status

```json
{
  "status": 2
}
```

Estados válidos:

- `0`: offline
- `1`: active
- `2`: available-for-cover

#### Response típica de `GET /auth/me/`

```json
{
  "id": 25,
  "name": "operador1",
  "role": "Operador",
  "role_id": 2,
  "session": {
    "id": 912,
    "station_id": 43,
    "station_number": "IT3",
    "sesion_in": "2026-04-20T09:12:31Z",
    "status": 1
  }
}
```

### 3.2 Flujo B: Platform auth sin estación

Usar este flujo para una plataforma central que solo necesita autenticar al usuario y devolver herramientas disponibles, sin crear una sesión diaria por estación.

Base path:

```text
/api/v1/platform/
```

Endpoints activos:

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| POST | `/auth/login/` | No | Login central sin estación |
| POST | `/auth/token/refresh/` | No | Renovar access token |
| GET | `/tools/` | Sí | Listar herramientas activas del usuario |

#### Request de platform login

```json
{
  "username": "supervisor1",
  "password": "1234"
}
```

#### Response de platform login

```json
{
  "access": "jwt-access-token",
  "refresh": "jwt-refresh-token",
  "user": {
    "id": 8,
    "name": "supervisor1",
    "role": "Supervisor",
    "role_id": 3
  },
  "tools": [
    {
      "slug": "daily-log",
      "name": "Daily Log",
      "description": "Registro operativo",
      "frontend_url": "http://localhost:5173",
      "icon": "clipboard"
    }
  ]
}
```

### 3.3 Recomendación de implementación frontend

Secuencia recomendada para Daily Log:

1. Resolver estación con `station_number` antes del login.
2. Obtener `station_id` a través de `/platform/station-config/`.
3. Ejecutar `POST /auth/login/` usando `station_id`.
4. Guardar `access`, `refresh` y `user`.
5. Configurar interceptor para refresh automático.
6. Consultar `GET /auth/me/` al iniciar la app para rehidratar sesión.

---

## 4. Milestone 2 — Gestión de eventos

Este milestone cubre el flujo principal de Daily Log: obtener catálogos, listar el daily del turno actual y crear eventos.

### 4.1 Catálogos requeridos antes de crear eventos

Base paths:

```text
/api/v1/catalogs/
/api/v1/events/
```

Endpoints activos:

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| GET | `/catalogs/sites/` | Sí | Cargar sitios |
| GET | `/catalogs/activities/` | Sí | Cargar actividades |
| GET | `/events/` | Sí | Cargar eventos del turno actual |
| POST | `/events/` | Sí | Crear evento |

#### Response de `GET /catalogs/sites/`

```json
[
  {
    "id": 101,
    "site_name": "101 - Site Name"
  }
]
```

#### Response de `GET /catalogs/activities/`

```json
[
  {
    "id": 44,
    "act_name": "START SHIFT"
  }
]
```

### 4.2 Listado del turno actual

`GET /api/v1/events/` devuelve los eventos del usuario autenticado desde su último `START SHIFT`.

#### Response de listado

```json
{
  "data": [
    {
      "id": 987,
      "site_name": "101 - Site Name",
      "activity_name": "CHECK CAMERA",
      "event_datetime": "2026-04-20T15:21:00Z",
      "event_status": "confirmed",
      "quantity": 1,
      "camera": "CAM-04",
      "description": "Camera checked"
    }
  ],
  "total": 1
}
```

### 4.3 Crear evento

#### Request

```json
{
  "site_id": 101,
  "activity_id": 44,
  "quantity": 1,
  "camera": "CAM-04",
  "description": "Camera checked"
}
```

#### Response

```json
{
  "id": 988,
  "site_name": "101 - Site Name",
  "activity_name": "START SHIFT",
  "event_datetime": "2026-04-20T15:31:04Z",
  "event_status": "confirmed",
  "quantity": 1,
  "camera": "CAM-04",
  "description": "Camera checked"
}
```

### 4.4 Reglas a considerar en frontend

- `user`, `event_datetime` y `event_status` se resuelven en backend.
- El frontend no debe enviar `user_id`.
- Si el sitio pertenece a grupo especial, el backend puede devolver `event_status="draft"` en lugar de `confirmed`.
- `quantity` acepta `0` o mayor.
- `description` tiene límite de 100 caracteres en validación actual.

### 4.5 Secuencia recomendada de pantalla Daily

1. Validar token o refrescarlo.
2. Cargar `/catalogs/sites/` y `/catalogs/activities/` en paralelo.
3. Cargar `/events/` para pintar el turno actual.
4. En creación exitosa, insertar el evento retornado o refrescar `/events/`.

---

## 5. Milestone 3 — Servicios de apoyo

Este milestone agrupa endpoints auxiliares que no son el núcleo del daily, pero sí destraban integración entre frontend y backend.

### 5.1 Resolución de estación desde frontend

El backend no puede leer directamente un archivo local del navegador como `C:\DailyLogConfig\station_config.json`. En web, la lectura del archivo debe ocurrir en el cliente y el cliente debe enviar el `station_number` al backend para validación.

Endpoint activo:

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| GET | `/platform/station-config/?station_number=IT3` | No | Resolver estación por número |

#### Response

```json
{
  "station_id": 43,
  "station_number": "IT3",
  "occupied": false,
  "is_active": null
}
```

#### Uso recomendado

1. El frontend lee `station_config.json`.
2. Obtiene `station_number`.
3. Llama a `/platform/station-config/`.
4. Usa `station_id` en `/auth/login/`.

### 5.2 Servicios para plataforma central

Endpoints activos:

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| GET | `/platform/tools/` | Sí | Herramientas activas según acceso |

Esto sirve para una shell o launcher central que enruta al usuario según el catálogo de tools disponible.

### 5.3 Servicios de Inventory

Base path:

```text
/api/v1/inventory/
```

Endpoints activos:

| Método | Endpoint |
|--------|----------|
| GET, POST | `/articles/` |
| GET, PATCH, DELETE | `/articles/{article_id}/` |
| GET | `/groups/` |
| GET, POST | `/activity-logs/` |
| GET | `/dashboard/stats/` |

### 5.4 Servicios de Schedules

Base path:

```text
/api/v1/schedules/
```

Endpoints activos:

| Método | Endpoint |
|--------|----------|
| GET | `/squads/` |
| POST | `/squads/{squad_id}/toggle-eligibility/` |
| GET | `/shift-types/` |
| GET | `/schedules/` |
| POST | `/schedules/upsert/` |
| POST | `/schedules/bulk/` |
| POST | `/schedules/delete-range/` |
| GET, POST | `/slots/` |
| DELETE | `/slots/{slot_id}/` |
| GET | `/slot-claims/` |
| POST | `/slot-claims/claim/` |
| POST | `/slot-claims/unclaim/` |
| GET, POST | `/cancellation-requests/` |
| POST | `/cancellation-requests/{request_id}/handle/` |
| GET, POST | `/notifications/` |
| POST | `/notifications/mark-read/` |

### 5.5 Qué entra en este milestone para frontend

- Resolver estación antes del login.
- Consumir `tools` si existe una plataforma central.
- Integrar inventory y schedules como módulos separados, reutilizando el mismo patrón JWT.
- Mantener cada app frontend desacoplada por feature y no mezclar contratos de Daily con Platform.

---

## 6. Milestone 4 — WebSockets a futuro

Hoy no hay canales websocket activos publicados para consumo frontend en producción funcional del proyecto. El diseño objetivo ya está claro, pero esta fase debe tratarse como futura.

### 6.1 Qué debería entrar en WebSockets

- Estado de estaciones en tiempo real.
- Notificaciones personales de covers y specials.
- Dashboard con métricas live.
- Noticias o broadcasts globales.

### 6.2 Canales previstos en el diseño

| Canal | Propósito |
|-------|-----------|
| `ws/stations/` | Estado de estaciones en tiempo real |
| `ws/notifications/{user_id}/` | Notificaciones del usuario |
| `ws/dashboard/` | KPIs en vivo |
| `ws/news/` | Broadcast global |

### 6.3 Recomendación técnica

- No introducir WebSockets para login ni para lectura inicial de estación.
- Mantener HTTP para auth, catálogos, eventos y resolución de estación.
- Introducir Channels cuando exista necesidad real de push server → client.
- Definir el contrato websocket después de estabilizar milestones 1 a 3.

---

## 7. Orden recomendado de implementación

1. Integrar `auth` daily con resolución previa de estación.
2. Integrar catálogos y CRUD base de eventos.
3. Separar módulos auxiliares por dominio: `platform`, `inventory`, `schedules`.
4. Cerrar manejo de refresh token y rehidratación de sesión.
5. Dejar WebSockets para una etapa posterior con Channels y Redis.

## 8. Checklist de salida por milestone

### Milestone 1

- Login exitoso con `station_id` válido.
- Persistencia de `access` y `refresh`.
- `GET /auth/me/` operativo al recargar.
- Logout cerrando sesión correctamente.

### Milestone 2

- Catálogos cargados desde backend.
- Listado del turno actual visible.
- Alta de evento operativa.
- Manejo de errores de validación en formulario.

### Milestone 3

- Resolución de estación desde `station_number` operativa.
- `tools` integrado si aplica.
- Módulos `inventory` y `schedules` desacoplados y usando el mismo JWT.

### Milestone 4

- Definición formal de eventos websocket.
- Estrategia de reconexión.
- Autorización de canal.
- Integración Channels + Redis.