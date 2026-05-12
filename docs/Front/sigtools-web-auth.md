# Sigtools Web Auth — Guía de integración para el Frontend

Documento de referencia completo para implementar el sistema de autenticación basado en cookie HttpOnly (`sig_token`) en cualquier aplicación web que consuma la API de SIG Tools.

---

## Índice

1. [Arquitectura y flujo general](#1-arquitectura-y-flujo-general)
2. [Cookie `sig_token` — propiedades y comportamiento](#2-cookie-sig_token--propiedades-y-comportamiento)
3. [Endpoints](#3-endpoints)
   - [POST /api/v1/web-auth/login/](#31-post-apiv1web-authlogin)
   - [POST /api/v1/web-auth/logout/](#32-post-apiv1web-authlogout)
   - [GET /api/v1/web-auth/me/](#33-get-apiv1web-authme)
4. [Tabla de niveles de acceso (access_level)](#4-tabla-de-niveles-de-acceso-access_level)
5. [Sistema de roles y permisos (app_roles)](#5-sistema-de-roles-y-permisos-app_roles)
   - [Roles disponibles](#51-roles-disponibles)
   - [Permisos por módulo](#52-permisos-por-módulo)
   - [Asignación de roles a usuarios](#53-asignación-de-roles-a-usuarios)
   - [Usuario de prueba](#54-usuario-de-prueba)
6. [Manejo de errores — catálogo completo](#6-manejo-de-errores--catálogo-completo)
7. [Configuración del cliente HTTP](#7-configuración-del-cliente-http)
8. [Implementación con Axios](#8-implementación-con-axios)
9. [Implementación con Fetch nativo](#9-implementación-con-fetch-nativo)
10. [Implementación con React (hook + contexto)](#10-implementación-con-react-hook--contexto)
11. [Flujo de sesión — ciclo de vida completo](#11-flujo-de-sesión--ciclo-de-vida-completo)
12. [Rutas protegidas — guard de autenticación](#12-rutas-protegidas--guard-de-autenticación)
13. [CORS — requisitos del backend](#13-cors--requisitos-del-backend)
14. [Coexistencia con otros sistemas de auth](#14-coexistencia-con-otros-sistemas-de-auth)
15. [Checklist de integración](#15-checklist-de-integración)

---

## 1. Arquitectura y flujo general

```
Frontend (Browser)                   API (Django)                  Servicios internos
─────────────────       ─────────────────────────────────       ──────────────────────
POST /login             →  Valida credenciales via LDAP      →   Active Directory sig.com
  {username, password}     Si OK:                                 (puerto 389, LDAP)
                              Genera token Sanctum-compatible
                              Guarda SHA256 en sigtools_beta
                           Responde 200 con user + access_level
                           ┗━━ Set-Cookie: sig_token=xxx; HttpOnly

GET /me                 →  Lee cookie sig_token automáticamente
                            Valida token contra sigtools_beta.personal_access_tokens
                           Responde 200 con perfil del usuario

POST /logout            →  Elimina fila en personal_access_tokens
                           Responde 204
                           ┗━━ Set-Cookie: sig_token=; Max-Age=0 (borra cookie)
```

**Punto clave**: El token nunca viaja en el body de las respuestas ni como `Authorization` header. El navegador lo gestiona automáticamente como cookie HttpOnly — **el JS del frontend no puede leerlo ni manipularlo**. Esto es por diseño: previene XSS.

---

## 2. Cookie `sig_token` — propiedades y comportamiento

| Propiedad      | Valor                              | Nota                                                              |
|----------------|------------------------------------|-------------------------------------------------------------------|
| `Name`         | `sig_token`                        | Nombre fijo — no configurable por el frontend                    |
| `HttpOnly`     | `true`                             | Inaccesible desde JavaScript (`document.cookie`)                 |
| `Secure`       | `false` (dev) / `true` (prod)      | En producción debe ser `true` — requiere HTTPS                   |
| `SameSite`     | `Lax`                              | Se envía en navegación de nivel superior, no en cross-site POST  |
| `Domain`       | mismo dominio del backend          | No se fuerza un dominio específico — hereda el del response       |
| `Max-Age`      | `28800` (8 horas)                  | El navegador la elimina automáticamente al vencer                 |
| `Path`         | `/`                                | Aplica a toda la API                                              |

**La cookie se envía automáticamente** con cada request al mismo dominio/origen — no requiere ninguna cabecera adicional en los requests a `/me/` ni a otros endpoints protegidos.

---

## 3. Endpoints

Base URL:

| Entorno | URL |
|---|---|
| **Local (mismo PC)** | `http://localhost:8000/api/v1/` |
| **Red LAN (otro PC en la oficina)** | `http://192.168.101.135:8000/api/v1/` |
| Producción | `https://<dominio>/api/v1/` |

### 3.1 `POST /api/v1/web-auth/login/`

Autentica al usuario via LDAP y establece la cookie de sesión.

**No requiere autenticación previa.**

#### Request

```http
POST /api/v1/web-auth/login/ HTTP/1.1
Content-Type: application/json

{
  "username": "hcruz",
  "password": "MiContraseñaAD"
}
```

| Campo      | Tipo     | Requerido | Descripción                                                  |
|------------|----------|-----------|--------------------------------------------------------------|
| `username` | `string` | ✅         | Usuario de Active Directory **sin** `@sig.com`               |
| `password` | `string` | ✅         | Contraseña de dominio AD                                     |

#### Response 200 — Login exitoso

```http
HTTP/1.1 200 OK
Content-Type: application/json
Set-Cookie: sig_token=42|a3f8c2...; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800
```

```json
{
  "user": {
    "id": 42,
    "name": "Héctor Cruz",
    "email": "hcruz@sig.com",
    "username": "hcruz"
  },
  "access_level": 1
}
```

| Campo          | Tipo      | Descripción                                                         |
|----------------|-----------|---------------------------------------------------------------------|
| `user.id`      | `integer` | ID del usuario en sigtools_beta                                     |
| `user.name`    | `string`  | Nombre completo (display name de AD)                                |
| `user.email`   | `string`  | Email corporativo                                                   |
| `user.username`| `string\|null` | Username en sigtools_beta (puede ser null si no está definido) |
| `access_level` | `integer` | Nivel de acceso según grupo AD (ver sección 4)                     |

> **Importante**: El token raw (`42|a3f8c2...`) **jamás aparece en el body**. La cookie es establecida por el navegador automáticamente — el frontend no necesita extraerla ni almacenarla.

#### Response 400 — Validación fallida

```json
{
  "username": ["This field is required."],
  "password": ["This field is required."]
}
```

#### Response 401 — Credenciales inválidas

```json
{
  "detail": "Invalid credentials."
}
```

O bien, si el usuario existe en AD pero no en sigtools_beta:

```json
{
  "detail": "LDAP authentication succeeded but this user has no account in the SIG Tools system. Contact your administrator."
}
```

---

### 3.2 `POST /api/v1/web-auth/logout/`

Revoca el token en la base de datos y borra la cookie del navegador.

**Requiere cookie `sig_token` válida.**

#### Request

```http
POST /api/v1/web-auth/logout/ HTTP/1.1
```

Body vacío — el token se lee de la cookie automáticamente.

#### Response 204 — Logout exitoso

```http
HTTP/1.1 204 No Content
Set-Cookie: sig_token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0
```

No body.

#### Response 401 — Sin sesión activa

```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### Response 401 — Cookie inválida o expirada

```json
{
  "detail": "Invalid or expired session cookie."
}
```

---

### 3.3 `GET /api/v1/web-auth/me/`

Retorna el perfil del usuario autenticado actualmente. Útil para:
- Verificar si la sesión sigue activa al cargar la app.
- Obtener datos del usuario después de un refresh de página.
- Hidratar el estado de auth del frontend sin re-login.

**Requiere cookie `sig_token` válida.**

#### Request

```http
GET /api/v1/web-auth/me/ HTTP/1.1
```

#### Response 200 — Sesión activa

```json
{
  "id": 42,
  "name": "Héctor Cruz",
  "email": "hcruz@sig.com",
  "username": "hcruz"
}
```

#### Response 401 — Sin sesión / cookie expirada

```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

## 4. Tabla de niveles de acceso (`access_level`)

El campo `access_level` del response de login indica el grupo AD del usuario. Se debe guardar en el estado del frontend para controlar visibilidad de secciones.

| `access_level` | Grupo AD                         | Descripción                                          |
|:--------------:|----------------------------------|------------------------------------------------------|
| `1`            | SIG ITTools                      | Acceso completo — administradores                    |
| `2`            | SIG ITTools CS                   | Acceso Customer Support                              |
| `3`            | SIG ITTools Full Viewer          | Solo lectura completa                                |
| `4`            | SIG ITTools Projects_Services    | Acceso Projects & Services                           |

**Lógica de prioridad**: Si el usuario pertenece a múltiples grupos, se asigna el de menor número (mayor privilegio). El nivel `1` tiene prioridad sobre todos los demás.

---

## 5. Sistema de roles y permisos (`app_roles`)

El `access_level` de AD controla el **nivel de acceso general** (quién puede entrar a la plataforma). Una vez dentro, los `app_roles` controlan **qué puede hacer** el usuario en cada módulo. Son dos capas independientes.

### 5.1 Roles disponibles

Los siguientes roles están definidos en `sigtools_beta.app_roles` y sincronizados en Supabase:

| `id` (UUID) | `name` | `label` | `description` |
|---|---|---|---|
| `ed87e26e-...` | `admin` | Administrador | Acceso total al sistema |
| `1115ed7c-...` | `designer` | Diseñador | Crea y edita proyectos tácticos |
| `34863cdc-...` | `field_tech` | Técnico de Campo | Acceso a Site Surveys en móvil |
| `c369ec46-...` | `inventory_op` | Operador Inventario | Ve y edita el inventario |
| `cf5c62cd-...` | `viewer` | Observador | Solo lectura en todas las aplicaciones |

### 5.2 Permisos por módulo

Cada permiso tiene un `key` en formato `<módulo>.<recurso>.<acción>`. El rol **admin** tiene todos los permisos asignados.

#### Módulo `installations`

| `key` | `label` | `category` |
|---|---|---|
| `installations.projects.view` | Ver proyectos | Proyectos |
| `installations.projects.create` | Crear proyectos | Proyectos |
| `installations.projects.edit` | Editar proyectos | Proyectos |
| `installations.projects.delete` | Eliminar proyectos | Proyectos |
| `installations.inventory.export` | Exportar a inventario | Inventario |
| `installations.map.view` | Ver mapa táctico | Mapa |
| `installations.map.edit` | Editar mapa | Mapa |
| `installations.surveys.view` | Ver Site Surveys | Site Surveys |
| `installations.surveys.capture` | Capturar fotos | Site Surveys |
| `installations.surveys.realtime` | Monitor en tiempo real | Site Surveys |
| `installations.pdf.view` | Ver PDF Editor | PDF Editor |

#### Módulo `inventory`

| `key` | `label` | `category` |
|---|---|---|
| `inventory.view` | Ver inventario | Inventario |
| `inventory.create` | Crear artículos | Inventario |
| `inventory.edit` | Editar artículos | Inventario |
| `inventory.delete` | Eliminar artículos | Inventario |
| `inventory.companies.manage` | Gestionar empresas | Empresas |
| `inventory.reports.view` | Ver reportes | Reportes |

#### Módulo `admin`

| `key` | `label` | `category` |
|---|---|---|
| `admin.users.view` | Ver usuarios | Usuarios |
| `admin.users.create` | Crear usuarios | Usuarios |
| `admin.users.edit` | Editar usuarios | Usuarios |
| `admin.users.delete` | Eliminar usuarios | Usuarios |
| `admin.roles.manage` | Gestionar roles | Roles |
| `admin.permissions.manage` | Gestionar permisos | Permisos |

### 5.3 Asignación de roles a usuarios

Los roles de aplicación se asignan en la tabla `user_app_roles` (sigtools_beta):

```
user_app_roles
├── id           BIGINT AUTO_INCREMENT PK
├── user_id      BIGINT  → FK a users.id
├── role_id      VARCHAR(36) → FK a app_roles.id (UUID)
└── granted_at   TIMESTAMP
```

Un usuario puede tener múltiples `app_roles`. Para consultar los roles de un usuario:

```sql
SELECT ar.name, ar.label
FROM user_app_roles uar
JOIN app_roles ar ON ar.id = uar.role_id
WHERE uar.user_id = <user_id>;
```

Para verificar si un usuario tiene un permiso específico:

```sql
SELECT COUNT(*) FROM user_app_roles uar
JOIN role_permissions rp ON rp.role_id = uar.role_id
JOIN permissions p ON p.id = rp.permission_id
WHERE uar.user_id = <user_id>
  AND p.key = 'installations.projects.create';
```

### 5.4 Usuario de prueba

Para testing sin Active Directory se creó el siguiente usuario en sigtools_beta:

| Campo | Valor |
|---|---|
| `id` | `67` |
| `username` | `test` |
| `name` | `Test Admin` |
| `email` | `test@sig.systems` |
| `app_role` | `admin` (todos los permisos) |

> **Nota**: Este usuario existe en la tabla `users` pero **no tiene credenciales AD válidas** — el login por cookie (`POST /web-auth/login/`) requiere LDAP. Para pruebas de endpoints protegidos sin LDAP, se puede generar un token manualmente en el shell del contenedor:
>
> ```bash
> docker exec daily-log-backend python manage.py shell -c "
> from apps.sigtools_auth.token_utils import generate_sanctum_token
> token = generate_sanctum_token(user_id=67, token_name='test-manual')
> print('Token:', token)
> "
> ```
>
> Luego usar el token como cookie en Postman/Insomnia: `sig_token = <token>`.

---

## 6. Manejo de errores — catálogo completo

| HTTP Status | `detail`                                                                                   | Causa                                                    | Acción en el frontend                        |
|:-----------:|--------------------------------------------------------------------------------------------|----------------------------------------------------------|----------------------------------------------|
| `400`       | `{"username": [...], "password": [...]}`                                                   | Campos faltantes o vacíos                                | Mostrar errores de validación en el form     |
| `401`       | `"Invalid credentials."`                                                                   | Usuario/contraseña AD incorrectos                        | Mostrar "Usuario o contraseña incorrectos"   |
| `401`       | `"LDAP authentication succeeded but this user has no account in the SIG Tools system..."` | Usuario en AD pero sin cuenta en sigtools                | Mostrar mensaje literal — contactar admin    |
| `401`       | `"Invalid or expired session cookie."`                                                     | Cookie existe pero el token fue revocado o venció en DB  | Redirigir a login y limpiar estado local     |
| `401`       | `"Authentication credentials were not provided."`                                          | Request a endpoint protegido sin cookie                  | Redirigir a login                            |
| `500`       | Cualquier error inesperado                                                                  | Error interno del servidor                               | Mostrar mensaje genérico, loguear en consola |

---

## 7. Configuración del cliente HTTP

**El requisito más crítico**: todos los requests deben incluir `credentials: 'include'` (fetch) o `withCredentials: true` (axios). Sin esto, el navegador **no envía ni guarda cookies cross-origin**.

También se requiere que el backend responda con `Access-Control-Allow-Credentials: true` y un origen explícito en `Access-Control-Allow-Origin` (el backend ya está configurado con `CORS_ALLOW_CREDENTIALS = True`).

---

## 8. Implementación con Axios

### 7.1 Instancia base configurada

```typescript
// src/lib/apiClient.ts
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  withCredentials: true,           // ← CRÍTICO: envía/recibe cookies cross-origin
  headers: {
    'Content-Type': 'application/json',
  },
})

// Interceptor: redirige a login si la sesión expiró
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Limpiar estado local y redirigir
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

### 7.2 Servicio de autenticación

```typescript
// src/services/authService.ts
import { apiClient } from '@/lib/apiClient'

export interface SigtoolsUser {
  id: number
  name: string
  email: string
  username: string | null
}

export interface LoginResponse {
  user: SigtoolsUser
  access_level: 1 | 2 | 3 | 4
}

export const authService = {
  /**
   * Autentica al usuario. En caso de éxito, el backend establece la cookie
   * sig_token automáticamente — el frontend nunca ve el token.
   */
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>('/web-auth/login/', {
      username,
      password,
    })
    return data
  },

  /**
   * Cierra sesión: revoca el token en el backend y borra la cookie.
   * Siempre intentar; ignorar errores 401 (ya expiró).
   */
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/web-auth/logout/')
    } catch {
      // Silenciar — si la cookie ya expiró, igual limpiar el estado local
    }
  },

  /**
   * Verifica si existe una sesión activa y retorna el perfil del usuario.
   * Usar en el mount inicial de la app para hidratar el estado de auth.
   * Retorna null si no hay sesión.
   */
  getMe: async (): Promise<SigtoolsUser | null> => {
    try {
      const { data } = await apiClient.get<SigtoolsUser>('/web-auth/me/')
      return data
    } catch (error: any) {
      if (error.response?.status === 401) return null
      throw error
    }
  },
}
```

---

## 9. Implementación con Fetch nativo

```typescript
// src/lib/apiFetch.ts
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    credentials: 'include',        // ← CRÍTICO
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (response.status === 204) return undefined as T

  const data = await response.json()

  if (!response.ok) {
    const message = data?.detail ?? 'Error desconocido'
    throw Object.assign(new Error(message), { status: response.status, data })
  }

  return data as T
}

// Funciones de auth
export const login = (username: string, password: string) =>
  apiFetch<{ user: SigtoolsUser; access_level: number }>('/web-auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

export const logout = () =>
  apiFetch<void>('/web-auth/logout/', { method: 'POST' })

export const getMe = () =>
  apiFetch<SigtoolsUser>('/web-auth/me/')
```

---

## 10. Implementación con React (hook + contexto)

### 9.1 Contexto de autenticación

```tsx
// src/context/AuthContext.tsx
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { authService, SigtoolsUser } from '@/services/authService'

interface AuthState {
  user: SigtoolsUser | null
  accessLevel: number | null
  isLoading: boolean
  isAuthenticated: boolean
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessLevel: null,
    isLoading: true,       // true durante la verificación inicial
    isAuthenticated: false,
  })

  // Al montar la app, verificar si hay sesión activa
  useEffect(() => {
    authService.getMe()
      .then((user) => {
        setState({
          user,
          accessLevel: null,     // /me no retorna access_level; guardarlo en localStorage al login
          isLoading: false,
          isAuthenticated: user !== null,
        })
      })
      .catch(() => {
        setState((s) => ({ ...s, isLoading: false }))
      })
  }, [])

  const login = async (username: string, password: string) => {
    const { user, access_level } = await authService.login(username, password)
    // Guardar access_level en localStorage (no es sensible — no es el token)
    localStorage.setItem('access_level', String(access_level))
    setState({
      user,
      accessLevel: access_level,
      isLoading: false,
      isAuthenticated: true,
    })
  }

  const logout = async () => {
    await authService.logout()
    localStorage.removeItem('access_level')
    setState({ user: null, accessLevel: null, isLoading: false, isAuthenticated: false })
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
```

### 9.2 Hook de acceso rápido

```tsx
// src/hooks/useAccessLevel.ts
import { useAuth } from '@/context/AuthContext'

/**
 * Retorna true si el usuario tiene acceso_level <= minLevel.
 * Menor número = mayor privilegio.
 * Ejemplo: hasAccess(2) → true si el usuario es nivel 1 o 2.
 */
export function useAccessLevel(minLevel: 1 | 2 | 3 | 4): boolean {
  const { accessLevel } = useAuth()
  if (accessLevel === null) return false
  return accessLevel <= minLevel
}
```

### 9.3 Formulario de login

```tsx
// src/pages/LoginPage.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await login(form.username.trim(), form.password)
      navigate('/dashboard')
    } catch (err: any) {
      // err.response?.data?.detail (axios) o err.message (fetch)
      const msg = err.response?.data?.detail ?? err.message ?? 'Error desconocido'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Usuario (sin @sig.com)"
        value={form.username}
        onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
        autoComplete="username"
        required
      />
      <input
        type="password"
        placeholder="Contraseña"
        value={form.password}
        onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
        autoComplete="current-password"
        required
      />
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <button type="submit" disabled={loading}>
        {loading ? 'Ingresando...' : 'Iniciar sesión'}
      </button>
    </form>
  )
}
```

---

## 11. Flujo de sesión — ciclo de vida completo

```
App monta
   │
   ▼
getMe() → 401?  ──── NO AUTENTICADO ──── Redirigir a /login
   │
   ▼ 200
Hidratar estado (user, access_level de localStorage)
   │
   ▼
Usuario navega normalmente
   │
   ├─── Cualquier request a endpoint protegido ─→ cookie se envía automáticamente
   │
   ├─── Recibe 401 "Invalid or expired session cookie."
   │         ▼
   │    Limpiar estado local → Redirigir a /login
   │
   └─── Usuario hace logout explícito
             ▼
         POST /logout/ → 204 → Limpiar estado → Redirigir a /login
```

### Rehydratación del `access_level`

El endpoint `/me/` no retorna `access_level` (solo el perfil). Para conocer el nivel sin re-login, guardarlo en `localStorage` al hacer login:

```typescript
// Al recibir el response de login:
localStorage.setItem('access_level', String(response.access_level))

// Al montar la app (después de verificar /me/):
const savedLevel = localStorage.getItem('access_level')
const accessLevel = savedLevel ? parseInt(savedLevel, 10) : null

// Al hacer logout — limpiar:
localStorage.removeItem('access_level')
```

> `access_level` no es información sensible — es solo un número que indica el grupo AD del usuario. No compromete la sesión si alguien lo modifica en localStorage, ya que los endpoints del backend tienen sus propias validaciones de permisos.

---

## 12. Rutas protegidas — guard de autenticación

```tsx
// src/components/ProtectedRoute.tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

interface Props {
  minAccessLevel?: 1 | 2 | 3 | 4
}

export default function ProtectedRoute({ minAccessLevel }: Props) {
  const { isAuthenticated, isLoading, accessLevel } = useAuth()

  if (isLoading) return <div>Cargando...</div>

  if (!isAuthenticated) return <Navigate to="/login" replace />

  if (minAccessLevel !== undefined && accessLevel !== null) {
    if (accessLevel > minAccessLevel) {
      return <Navigate to="/forbidden" replace />
    }
  }

  return <Outlet />
}
```

```tsx
// src/App.tsx — ejemplo de rutas
import { Routes, Route } from 'react-router-dom'
import ProtectedRoute from '@/components/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import Dashboard from '@/pages/Dashboard'
import AdminPanel from '@/pages/AdminPanel'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Cualquier usuario autenticado */}
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<Dashboard />} />
      </Route>

      {/* Solo nivel 1 y 2 */}
      <Route element={<ProtectedRoute minAccessLevel={2} />}>
        <Route path="/admin" element={<AdminPanel />} />
      </Route>
    </Routes>
  )
}
```

---

## 13. CORS — requisitos del backend

El backend ya tiene configurado:

```python
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    # ...
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://192\.168\.101\.\d+:\d+$",   # ← cubre TODA la subred 192.168.101.x
    r"^https?://localhost:\d+$",
]
```

### Conexión desde otro PC en la red local

El regex `192\.168\.101\.\d+:\d+` ya permite que **cualquier PC en la subred 192.168.101.x** acceda al backend — no hay que tocar nada en el backend.

Desde el frontend en otro PC, configurar la variable de entorno apuntando al servidor:

```bash
# .env (en el proyecto frontend, en el otro PC)
VITE_API_URL=http://192.168.101.135:8000
```

> **Requisito**: el otro PC debe estar en la misma red (Wi-Fi o LAN de la oficina). El puerto `8000` debe ser accesible — si hay firewall de Windows en el servidor, habilitarlo con:
> ```powershell
> New-NetFirewallRule -DisplayName "Django Dev" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
> ```

### Agregar origen de producción

Para **agregar un nuevo origen** de producción (ej: `https://sigtools.sig.com`), agregar al env var `CORS_ALLOWED_ORIGINS` en el contenedor Docker o en el `.env` de producción.

**El frontend NO puede usar `withCredentials: true` + `Access-Control-Allow-Origin: *`** — el navegador lo rechaza. El backend debe listar los orígenes explícitamente, lo cual ya hace.

---

## 14. Coexistencia con otros sistemas de auth

La API tiene **tres sistemas de autenticación que coexisten sin interferirse**:

| Sistema               | Mecanismo                               | Quién lo usa                                |
|-----------------------|-----------------------------------------|---------------------------------------------|
| Django Admin          | Sesión HTTP clásica (`sessionid`)       | `/admin/` — solo en navegador interno       |
| DailyLog JWT          | `Authorization: Bearer <token>`         | App móvil / DailyLog SPA                    |
| **Web Cookie Auth**   | **Cookie HttpOnly `sig_token`**         | **Cualquier webapp que use este doc**       |

El orden de evaluación por request:
1. Si hay cookie `sig_token` → se usa `SigtoolsCookieAuthentication`
2. Si hay header `Authorization: Bearer` → se usa `JWTAuthentication`
3. Si ninguno → el request queda anónimo (403 en endpoints protegidos)

Un mismo endpoint puede ser accedido por ambos sistemas (el que corresponda según el cliente que llame).

---

## 15. Checklist de integración

Marcar cada ítem antes de considerar la implementación completa:

- [ ] El cliente HTTP tiene `withCredentials: true` (Axios) o `credentials: 'include'` (fetch) en **todos** los requests
- [ ] El origen del frontend está en la lista `CORS_ALLOWED_ORIGINS` del backend
- [ ] `getMe()` se llama al montar la app (para detectar sesión existente después de refresh)
- [ ] El `access_level` se guarda en `localStorage` al login y se limpia al logout
- [ ] Los errores 401 en requests autenticados redirigen a `/login` y limpian el estado local
- [ ] El formulario de login muestra el error `detail` del response (no un mensaje genérico)
- [ ] El formulario de login usa `autocomplete="username"` y `autocomplete="current-password"` (buenas prácticas de accesibilidad/browsers)
- [ ] El logout llama a `POST /logout/` antes de redirigir (para revocar el token en DB)
- [ ] En producción: la variable `SIGTOOLS_COOKIE_SECURE=true` está seteada en el backend y el frontend corre sobre HTTPS
- [ ] Rutas protegidas usan el guard con `minAccessLevel` donde corresponde

---

## Variables de entorno necesarias en el frontend

```bash
# .env — mismo PC (desarrollo local)
VITE_API_URL=http://localhost:8000

# .env — otro PC en la red local (apuntar al servidor en 192.168.101.135)
VITE_API_URL=http://192.168.101.135:8000

# .env — producción
VITE_API_URL=https://<dominio>
```

No hay ninguna otra variable de entorno relacionada con auth — el token lo maneja el navegador de forma automática.
