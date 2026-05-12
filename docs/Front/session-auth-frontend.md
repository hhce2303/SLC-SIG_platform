# Sesiones y Autenticación — Guía para Frontend

> **Base URL auth:** `http://192.168.101.135:8000/web-auth`  
> **Mecanismo:** Cookie HttpOnly `sig_token` (Sanctum-compatible)

---

## Resumen rápido

| ¿Qué? | ¿Cómo? |
|---|---|
| Autenticarse | `POST /web-auth/login/` con `{username, password}` |
| Verificar sesión al cargar la app | `GET /web-auth/me/` |
| Cerrar sesión (dispositivo actual) | `POST /web-auth/logout/` |
| Cerrar sesión en todos los dispositivos | `POST /web-auth/logout-all/` |
| Token (mismo origen) | Cookie HttpOnly `sig_token` — el navegador la gestiona automáticamente |
| Token (cross-origin) | `access_token` del body de login → `Authorization: Bearer <token>` |

---

## ¿Cookie o Bearer? — Cuándo usar cada uno

| Escenario | Mecanismo recomendado |
|---|---|
| Frontend y backend en el **mismo dominio/host** | Cookie HttpOnly (automática con `withCredentials: true`) |
| Frontend en `localhost:5173`, backend en `192.168.101.135:8000` | **Bearer token** — la cookie no se envía cross-origin con `SameSite=Lax` |
| Testing con Postman / Thunder Client | Bearer token |

El backend acepta ambos en el mismo endpoint — primero verifica el cookie, si no está usa el header `Authorization: Bearer`.

---

## Endpoints

### `POST /web-auth/login/`

**Body:**
```json
{ "username": "hcruz", "password": "..." }
```

> `username` es el nombre de usuario de AD, **sin** `@sig.com`

**Response `200`:**
```json
{
  "user": {
    "id": 67,
    "name": "Hector Cruz",
    "email": "hcruz@sig.systems",
    "username": "hcruz"
  },
  "access_level": 4,
  "access_token": "11|abc123..."
}
```

> El servidor también setea el cookie HttpOnly `sig_token` automáticamente.  
> **`access_token` es el token en formato Sanctum (`{id}|{plaintext}`).** Úsalo como `Authorization: Bearer <token>` cuando el frontend esté en un origen distinto al backend (cross-origin). Guárdalo en memoria o `sessionStorage` — nunca en `localStorage`.

**Response `401`:**
```json
{ "detail": "Credenciales inválidas." }
```

---

### `GET /web-auth/me/`

Verifica si hay sesión activa y retorna los datos del usuario.  
Llama esto al iniciar la app para saber si el usuario ya está autenticado.

**Response `200`:**
```json
{
  "id": 67,
  "name": "Hector Cruz",
  "email": "hcruz@sig.systems",
  "username": "hcruz"
}
```

**Response `403`:** Cookie ausente o expirada → redirigir al login.

---

### `POST /web-auth/logout/`

Revoca el token del dispositivo actual y borra la cookie.

**Response `204`:** Sin body.

---

### `POST /web-auth/logout-all/`

Revoca **todos** los tokens del usuario (útil para cerrar todas las sesiones activas).

**Response `200`:**
```json
{ "message": "Logged out from 3 session(s)." }
```

---

## Implementación en el frontend

### Opción A — Cookie (mismo origen / Vite proxy)

```ts
// api.ts — instancia de axios global
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://192.168.101.135:8000',
  withCredentials: true,   // envía la cookie sig_token en cada request
})

export default api
```

---

### Opción B — Bearer token (cross-origin, recomendado para dev)

```ts
// auth.ts — manejo de token en memoria
let _token: string | null = null

export function setToken(t: string) { _token = t }
export function clearToken()        { _token = null }

// api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://192.168.101.135:8000',
  withCredentials: true,  // también envía cookie si está disponible
})

// Agrega el token Bearer automáticamente si está en memoria
api.interceptors.request.use((config) => {
  if (_token) {
    config.headers['Authorization'] = `Bearer ${_token}`
  }
  return config
})

export default api
```

---

### Login

```ts
async function login(username: string, password: string) {
  const res = await api.post('/api/v1/web-auth/login/', { username, password })
  // Guardar el token para requests cross-origin
  setToken(res.data.access_token)
  // La cookie HttpOnly también fue seteada automáticamente por el servidor.
  return res.data  // { user, access_level, access_token }
}
```

---

### Verificar sesión al iniciar la app

```ts
// Llamar esto en el componente raíz o en el router guard
async function checkSession() {
  try {
    const res = await api.get('/api/v1/web-auth/me/')
    return res.data  // { id, name, email, username }
  } catch {
    // 401/403 = sin sesión → ir al login
    return null
  }
}

// Ejemplo en Vue
onMounted(async () => {
  const user = await checkSession()
  if (!user) router.push('/login')
  else store.setUser(user)
})
```

> ⚠️ Si el frontend se recarga (F5), el token en memoria se pierde. Opciones:  
> 1. Guardar en `sessionStorage` (persiste en la pestaña pero no entre pestañas)  
> 2. Volver a llamar al login con credenciales guardadas  
> 3. Usar el cookie si el frontend está en el mismo origen

---

### Logout

```ts
async function logout() {
  await api.post('/api/v1/web-auth/logout/')
  clearToken()
  store.clearUser()
  router.push('/login')
}
```

---

### Logout de todas las sesiones

```ts
async function logoutAll() {
  const res = await api.post('/api/v1/web-auth/logout-all/')
  console.log(res.data.message)  // "Logged out from 3 session(s)."
  clearToken()
  store.clearUser()
  router.push('/login')
}
```

---

### Interceptor para manejar expiración automática

```ts
// Redirige al login si cualquier endpoint retorna 401 o 403
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      clearToken()
      store.clearUser()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)
```

---

## Cómo funciona la persistencia

```
Usuario refresca la página
        │
        ▼
Tu app llama GET /web-auth/me/  (con credentials: 'include')
        │
        ├── Cookie sig_token presente y válida (< 8 h sin actividad)
        │       → 200 OK + datos del usuario
        │       → app inicializa normalmente
        │
        └── Cookie ausente o expirada
                → 403 Forbidden
                → redirigir al login
```

**La cookie sobrevive a:**
- Refrescar la página (F5)
- Abrir una nueva pestaña del mismo dominio
- Cerrar y volver a abrir el navegador (mientras no expire)

**La cookie expira:**
- 8 horas sin actividad (configurable en el servidor)
- Al llamar `/web-auth/logout/` o `/web-auth/logout-all/`

---

## Tipos TypeScript

```ts
interface SigtoolsUser {
  id: number
  name: string
  email: string
  username: string | null
}

interface LoginResponse {
  user: SigtoolsUser
  access_level: number  // 1-4 según nivel de acceso LDAP
}
```

---

## Notas importantes

- **No guardes el token en `localStorage` ni en ningún estado JS** — ya lo gestiona el navegador como cookie HttpOnly. JS no puede leerlo (protección contra XSS).
- `credentials: 'include'` (o `withCredentials: true`) es **obligatorio** en cada request. Sin eso la cookie no se envía.
- `access_level` viene del LDAP de la empresa y puede variar según el grupo del usuario (1 = básico, 4 = administrador). Úsalo para mostrar/ocultar secciones en el UI.
- Si el servidor está en un dominio distinto al frontend (ej: `localhost:3000` vs `192.168.101.135:8000`), el CORS ya está configurado para aceptar credenciales (`CORS_ALLOW_CREDENTIALS = True`). Solo asegúrate de que tu origen esté en `CORS_ALLOWED_ORIGINS` en el servidor.
