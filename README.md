    # DAILY LOG BACKEND — Master Context Document

> **Propósito:** Este documento es la fuente de verdad para cualquier agente IA o desarrollador que trabaje en este proyecto. Debe leerse al inicio de cada conversación para mantener contexto completo.

> **Manual de conexión frontend/backend:** ver `docs/manual-conexion-milestones.md` para la guía operativa por etapas de integración.

---

## 1. VISIÓN DEL PROYECTO

**Daily Log System** es un sistema empresarial de monitoreo y bitácora de operaciones para una central de estaciones de vigilancia (SIG Systems). Actualmente existe como una **aplicación de escritorio Python/Tkinter** (`proyecto_app`) que se conecta directamente a MySQL. El objetivo es **migrar la lógica de negocio a un backend Django REST API** para servir una futura interfaz web, manteniendo compatibilidad con la base de datos existente.

### Qué existe hoy (proyecto_app)
- Aplicación de escritorio Python con CustomTkinter
- Arquitectura MVC modular (`src/modules/`, `src/core/`, `src/ui/`)
- Conexión directa a MySQL vía `pymysql` con connection pooling
- ~120 consultas SELECT, ~40 INSERT, ~50 UPDATE, ~10 DELETE
- Cache en memoria con TTL (estático/semi/dinámico)
- Sistema de auditoría por sesión (archivos .log)
- Polling periódico a BD para actualizaciones en tiempo real
- Roles: Operador, Supervisor, Lead Supervisor, Admin

### Qué se construirá (daily-log-backend)
- Django REST Framework API
- Misma base de datos MySQL (`sig_dailylogs`) — modelos `managed = False` para tablas existentes
- Autenticación JWT (tokens)
- Permisos por rol mapeados a Django Groups/Permissions
- WebSockets (Django Channels) para reemplazar polling
- Celery para tareas asíncronas (healthcheck, limpieza)
- Cache con Redis reemplazando el cache en memoria
- Auditoría centralizada en BD (no en archivos)

---

## 2. BASE DE DATOS EXISTENTE (MySQL)

**Host:** `72.167.56.142` | **DB:** `sig_dailylogs` | **Engine:** MySQL 5.7+ | **Puerto:** 3306

### 2.1 Tablas Principales (Modernas — prefijo `daily_`)

| Tabla | Propósito | Operaciones frecuentes |
|-------|-----------|----------------------|
| `daily_users` | Usuarios del sistema (ID_user, user_password, ID_user_rol) | Auth, permisos |
| `daily_users_names` | Nombres de usuario (ID_user, user_name) | Lookup constante |
| `daily_user_rol` | Roles (ID_user_rol, user_rol_name) | Permisos |
| `daily_sesions` | Sesiones activas/históricas (ID_sesion, ID_user, ID_station, sesion_in, sesion_out, sesion_active, sesion_status) | Login/logout, estado |
| `daily_stations_info` | Info de estaciones (station_number) | Lookup |
| `daily_stations_map` | Mapa estación-usuario (station_ID, station_user, is_active) | Asignación |
| `daily_sites` | Sitios monitoreados (ID_site, ID_group, site_name, site_dns, site_timezone) | Eventos, HC |
| `daily_activities` | Catálogo de actividades (ID_activity, act_name) | Eventos |
| `daily_events` | Bitácora de eventos (ID_event, ID_user, ID_site, ID_activity, event_datetime, event_status, quantity, camera, description) | CRUD principal |
| `daily_specials` | Eventos especiales (ID_special, ID_event, ID_user, ID_supervisor, spec_datetime, spec_status, spec_description) | Supervisor review |
| `daily_covers_solicitudes` | Solicitudes de cover (ID_cover, ID_user, cover_time_request, ID_station, approved, active) | Cover workflow |
| `daily_covers_completed` | Covers realizados (ID_cover_complete, ID_user, ID_user_cover_by, cover_in, cover_out) | Cover tracking |
| `daily_breaks` | Breaks programados (ID_break, ID_user_covered, ID_user_covering, break_datetime, active, ID_supervisor) | Break management |
| `daily_news` | Noticias/alertas (ID_news, news_type, news_info, news_urgency, active) | Admin CRUD |
| `daily_supervisor_station_selection` | Asignación manual supervisor-estación | Central station |
| `daily_supervisor_stations_ranges` | Rangos automáticos supervisor-estación (ID_station_start, ID_station_end, active) | Central station |
| `daily_hc_sites` | Healthcheck por sitio (total_cameras, inactive_cameras, estado_check) | HC module |
| `daily_hc_tickets` | Tickets de soporte (ticket_id, ID_site, ID_supervisor) | HC tickets |

### 2.2 Tablas Legacy (sin prefijo — en proceso de deprecación)

| Tabla | Equivalente moderno | Estado |
|-------|---------------------|--------|
| `Eventos` | `daily_events` | Aún usado en some modules |
| `user` | `daily_users` + `daily_users_names` | Legacy auth |
| `Estaciones` | `daily_stations_map` | Legacy |
| `sitios` | `daily_sites` | Legacy HC |
| `Actividades` | `daily_activities` | Legacy |
| `sesion` | `daily_sesions` | Legacy |
| `specials` | `daily_specials` | Dual-write in some places |
| `covers_programados` | `daily_covers_solicitudes` | Legacy |
| `stations_map` | `daily_stations_map` | Legacy |
| `timezones` | — | Referencia offsets |
| `time_zone_config` | — | Config TZ |

### 2.3 Relaciones Clave (FK implícitas — no hay FK en BD)

```
daily_users.ID_user ──────── daily_users_names.ID_user
daily_users.ID_user_rol ──── daily_user_rol.ID_user_rol
daily_sesions.ID_user ────── daily_users.ID_user
daily_sesions.ID_station ─── daily_stations_info.ID_station
daily_events.ID_user ─────── daily_users.ID_user
daily_events.ID_site ─────── daily_sites.ID_site
daily_events.ID_activity ─── daily_activities.ID_activity
daily_specials.ID_event ──── daily_events.ID_event
daily_specials.ID_user ───── daily_users.ID_user
daily_specials.ID_supervisor  daily_users.ID_user
daily_covers_solicitudes.ID_user ── daily_users.ID_user
daily_covers_completed.ID_user ──── daily_users.ID_user
daily_breaks.ID_user_covered ────── daily_users.ID_user
daily_breaks.ID_user_covering ───── daily_users.ID_user
daily_hc_tickets.ID_site ────────── daily_sites.ID_site
daily_stations_map.station_ID ───── daily_stations_info.ID_station
```

> **IMPORTANTE:** La BD NO tiene foreign keys declaradas. Las relaciones son implícitas vía JOINs en el código. Django las modelará con `db_constraint=False`.

---

## 3. SISTEMA DE ROLES Y PERMISOS

### 3.1 Roles del Sistema

| Rol | ID | Acceso principal |
|-----|----|-----------------|
| **Operador** | 2 | Daily events (CRUD), solicitar covers, specials (crear) |
| **Supervisor** | 3 | Specials (revisar/aprobar), aprobar covers, asignar estaciones |
| **Lead Supervisor** | 4 | Todo de Supervisor + reportes + gestión de supervisores |
| **Admin** | 1 | Panel completo, CRUD tablas, forzar logout, métricas |

### 3.2 Matriz de Permisos por Módulo

| Endpoint/Módulo | Operador | Supervisor | Lead Supervisor | Admin |
|-----------------|----------|------------|-----------------|-------|
| `events/` | CRUD propio | Solo lectura | Solo lectura | Completo |
| `specials/` | Crear | Revisar/marcar | Gestionar/transferir | Completo |
| `covers/solicitudes/` | Crear | Aprobar/rechazar | Gestionar | Completo |
| `covers/completed/` | Ver propios | Ver asignados | Ver todos | Completo |
| `breaks/` | Ver propios | CRUD | CRUD | Completo |
| `sessions/` | Propia | Ver estaciones asignadas | Ver todas | Completo + force logout |
| `stations/` | — | Asignar (propias) | Asignar (todas) | Completo |
| `healthcheck/` | — | CRUD asignados | Completo | Completo |
| `news/` | Solo lectura | Solo lectura | Crear | CRUD |
| `admin/metrics/` | — | — | — | Completo |
| `audit/` | — | — | — | Completo |
| `users/` | Perfil propio | Ver operadores | Ver todos | CRUD |
| `reports/` | — | — | Completo | Completo |

---

## 4. ARQUITECTURA DJANGO PROPUESTA

### 4.1 Estructura de Proyecto

```
daily-log-backend/
├── manage.py
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py            # Settings compartidos
│       ├── development.py     # DEBUG=True, CORS abierto
│       ├── production.py      # Security headers, allowed hosts
│       └── test.py            # SQLite, fixtures
├── apps/
│   ├── core/                  # Modelos compartidos, mixins, utils
│   │   ├── models/            # User, Role, Station, Site, Activity
│   │   ├── serializers/
│   │   ├── permissions.py     # IsOperator, IsSupervisor, IsAdmin, etc.
│   │   ├── pagination.py
│   │   ├── exceptions.py
│   │   └── middleware/
│   │       ├── audit.py       # Request/response logging
│   │       └── timezone.py    # Timezone-aware requests
│   ├── users/                 # Autenticación y gestión de usuarios
│   │   ├── models.py          # Proxy sobre daily_users + JWT
│   │   ├── serializers.py
│   │   ├── views.py           # Login, logout, perfil, cambiar status
│   │   ├── urls.py
│   │   └── services.py        # Lógica de sesión, station mapping
│   ├── logs/                  # Módulo principal: Daily Events
│   │   ├── models.py          # Event, Activity, Site (managed=False)
│   │   ├── serializers.py
│   │   ├── views.py           # CRUD eventos, confirmar, filtrar
│   │   ├── urls.py
│   │   ├── services.py        # create_event, confirm_event, draft->confirmed flow
│   │   └── filters.py
│   ├── notifications/         # Specials + News + Alertas
│   │   ├── models.py          # Special, News
│   │   ├── serializers.py
│   │   ├── views.py           # CRUD specials, asignar supervisor, marcar
│   │   ├── urls.py
│   │   ├── services.py        # auto_assign_supervisor, transfer_specials
│   │   └── consumers.py       # WebSocket para notificaciones real-time
│   ├── audit/                 # Auditoría y sesiones
│   │   ├── models.py          # AuditLog (nuevo), Session (daily_sesions)
│   │   ├── serializers.py
│   │   ├── views.py           # Consulta de sesiones, eventos audit
│   │   ├── urls.py
│   │   └── services.py
│   └── reports/               # Reportes y métricas
│       ├── models.py          # Vistas de BD o queries complejas
│       ├── serializers.py
│       ├── views.py           # Dashboard metrics, gráficas, KPIs
│       ├── urls.py
│       └── services.py        # Agregaciones, cálculos
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.celery
│   └── docker-compose.yml
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   ├── production.txt
│   └── test.txt
└── docs/
    └── api/                   # OpenAPI / Swagger auto-generado
```

### 4.2 Stack Tecnológico

| Componente | Tecnología | Justificación |
|-----------|------------|---------------|
| Framework | Django 5.x | Ecosistema maduro, ORM potente, admin panel |
| API | Django REST Framework 3.15+ | Estándar para REST APIs en Django |
| Auth | `djangorestframework-simplejwt` | Tokens JWT stateless |
| Real-time | Django Channels + `channels-redis` | WebSockets para reemplazar polling |
| Cache | Redis via `django-redis` | Reemplaza cache en memoria, compartido entre workers |
| Task Queue | Celery + Redis broker | Healthcheck polling, limpieza, reportes async |
| DB | MySQL 5.7+ (existente) | `mysqlclient` como driver (más rápido que pymysql) |
| Docs | `drf-spectacular` | OpenAPI 3.0 schema + Swagger UI |
| CORS | `django-cors-headers` | Permitir frontend en dominio diferente |
| Filtros | `django-filter` | Filtrado declarativo en ViewSets |
| Env | `python-decouple` o `django-environ` | Variables de entorno, no hardcodear secrets |

### 4.3 Convenciones de Código

```python
# === MODELOS ===
# managed = False para tablas existentes
# db_table explícito
# db_constraint = False en ForeignKey
class DailyEvent(models.Model):
    class Meta:
        managed = False
        db_table = 'daily_events'

# === SERVICIOS ===
# Toda lógica de negocio en services.py, NUNCA en views
# Funciones puras cuando sea posible
# transaction.atomic() para operaciones multi-tabla
def create_and_confirm_event(user_id: int, payload: dict) -> DailyEvent:
    with transaction.atomic():
        event = DailyEvent.objects.create(**payload, event_status='draft')
        event.event_status = 'confirmed'
        event.save(update_fields=['event_status'])
    return event

# === VIEWS ===
# ViewSets para CRUD estándar
# @action para operaciones custom
# Permisos explícitos en cada view
class EventViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOperatorOrReadOnly]
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None): ...

# === SERIALIZERS ===
# Validaciones de dominio aquí
# Nested serializers para lecturas, PK para escrituras
class EventSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.site_name', read_only=True)
    
# === PERMISOS ===
# Clases custom basadas en rol
class IsOperator(BasePermission):
    def has_permission(self, request, view):
        return request.user.role.user_rol_name == 'Operador'
```

---

## 5. MAPEO PROYECTO_APP → DJANGO APPS

### 5.1 Funciones reutilizables directamente

Estas funciones del proyecto_app contienen lógica de negocio pura (sin Tkinter) que puede portarse casi 1:1:

| Función original | Ubicación proyecto_app | App Django destino | Notas |
|-----------------|----------------------|-------------------|-------|
| `create_event()` | `daily_events/models/daily_model.py` | `apps/logs/services.py` | Flujo draft→confirmed |
| `confirm_event()` | `daily_events/models/daily_model.py` | `apps/logs/services.py` | |
| `request_covers()` | `covers/models/cover_model.py` | `apps/logs/services.py` | Workflow covers |
| `insertar_cover()` | `covers/models/cover_model.py` | `apps/logs/services.py` | Multi-tabla |
| `start_break_cover()` | `breaks/models/breaks_model.py` | `apps/logs/services.py` | Transaccional |
| `add_break_to_db()` | `breaks/models/breaks_model.py` | `apps/logs/services.py` | |
| `insert_special_from_event()` | `specials/models/specials_model.py` | `apps/notifications/services.py` | Auto-assign supervisor |
| `get_supervisor_by_station()` | `specials/models/specials_model.py` | `apps/notifications/services.py` | Lógica auto+manual |
| `update_special_status()` | `specials/models/specials_model.py` | `apps/notifications/services.py` | |
| `authenticate_user()` | `authentication/models/login_model.py` | `apps/users/services.py` | Adaptar a Django auth |
| `new_sesion_entry()` | `authentication/models/login_model.py` | `apps/users/services.py` | |
| `do_logout()` | `authentication/models/login_model.py` | `apps/users/services.py` | + free_station |
| `get_dashboard_metrics()` | `admin/models/admin_model.py` | `apps/reports/services.py` | Queries agregadas |
| `get_covers_graph_data()` | `admin/models/admin_model.py` | `apps/reports/services.py` | |
| `get_activity_graph_data()` | `admin/models/admin_model.py` | `apps/reports/services.py` | |
| `load_sessions()` | `admin/models/audit_model.py` | `apps/audit/services.py` | Filtros complejos |
| `load_events()` | `admin/models/audit_model.py` | `apps/audit/services.py` | |

### 5.2 Funciones que requieren adaptación significativa

| Función | Razón | Estrategia Django |
|---------|-------|-------------------|
| `preload_static_data()` | Cache en memoria → Redis | `django-redis` + cache framework |
| `run_in_background()` | Tkinter threading → async | Celery task o Django async view |
| `check_station_availability()` | Polling → WebSocket push | Django Channels consumer |
| `force_logout_user()` | Actualiza BD → también invalida JWT | Blacklist token + update BD |
| `auto_login()` | Sesión Tkinter → JWT token | Custom auth backend |
| `normalize_tickets()` | JSON file → Redis o BD | Celery periodic task |
| Todo el polling de estaciones | Timer threads → push | Channels group broadcast |

---

## 6. API ENDPOINTS PLANIFICADOS

### 6.1 Autenticación (`/api/v1/auth/`)

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| POST | `/login/` | Autenticar, crear sesión, retornar JWT | Público |
| POST | `/logout/` | Cerrar sesión, liberar estación | Autenticado |
| POST | `/token/refresh/` | Refrescar access token | Autenticado |
| GET | `/me/` | Perfil del usuario autenticado | Autenticado |
| PATCH | `/me/status/` | Cambiar estado (lista, breaks, etc.) | Autenticado |

### 6.2 Eventos Daily (`/api/v1/events/`)

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| GET | `/` | Listar eventos (filtros: user, site, date, activity) | Autenticado |
| POST | `/` | Crear evento (draft → confirmed) | Operador |
| GET | `/{id}/` | Detalle de evento | Autenticado |
| PATCH | `/{id}/` | Actualizar evento | Operador (propio) |
| POST | `/{id}/confirm/` | Confirmar evento draft | Operador (propio) |
| GET | `/my-daily/` | Eventos del turno actual del usuario | Operador |

### 6.3 Specials (`/api/v1/specials/`)

| Método | Endpoint | Descripción | Estado | Roles |
|--------|----------|-------------|--------|-------|
| GET | `/supervisor/` | Specials pendientes del supervisor autenticado (excluye 'done') | ✅ Implementado | Supervisor+ |
| PATCH | `/{id}/mark/` | Marcar (`done`/`flagged`) o desmarcar (`null`) un special | ✅ Implementado | Supervisor+ |
| POST | `/` | Crear special desde evento | Planificado | Operador |
| POST | `/{id}/assign/` | Asignar supervisor | Planificado | Lead Supervisor |
| POST | `/transfer/` | Transferir specials entre supervisores | Planificado | Lead Supervisor |
| GET | `/unassigned/` | Specials sin supervisor asignado | Planificado | Lead Supervisor |

> **Nota de implementación (v1):** El endpoint `GET /supervisor/` ejecuta una sola query con JOINs a `daily_sites`, `daily_activities` y `daily_users_names` vía `select_related`. No hay N+1. El frontend **no debe** hacer polling más frecuente que cada 30 s.
> Manual de conexión frontend → `docs/specials-supervisor-api.md`

### 6.4 Covers y Breaks (`/api/v1/covers/`, `/api/v1/breaks/`)

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| GET | `/covers/requests/` | Solicitudes de cover activas | Autenticado |
| POST | `/covers/requests/` | Solicitar cover | Operador |
| POST | `/covers/requests/{id}/approve/` | Aprobar solicitud | Supervisor |
| POST | `/covers/requests/{id}/cancel/` | Cancelar solicitud | Operador (propio) |
| GET | `/covers/completed/` | Covers realizados | Autenticado |
| POST | `/covers/execute/` | Registrar cover (cover_in) | Autenticado |
| POST | `/covers/{id}/exit/` | Salir de cover (cover_out) | Autenticado |
| GET | `/breaks/` | Breaks programados del día | Autenticado |
| POST | `/breaks/` | Programar break | Supervisor |
| DELETE | `/breaks/{id}/` | Eliminar break | Supervisor |
| POST | `/breaks/{id}/start/` | Iniciar break (ejecutar cover) | Autenticado |

### 6.5 Sesiones y Estaciones (`/api/v1/sessions/`, `/api/v1/stations/`)

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| GET | `/sessions/` | Listar sesiones (filtros: active, user, station) | Supervisor+ |
| GET | `/sessions/active/` | Sesiones activas con detalle | Supervisor+ |
| POST | `/sessions/{id}/force-logout/` | Forzar logout | Admin |
| GET | `/stations/` | Estado de todas las estaciones | Supervisor+ |
| GET | `/stations/map/` | Mapa estación-usuario-supervisor | Supervisor+ |
| POST | `/stations/assign/` | Asignar estación a supervisor | Supervisor |
| POST | `/stations/ranges/` | Configurar rangos automáticos | Supervisor |

### 6.6 Healthcheck (`/api/v1/healthcheck/`)

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| GET | `/sites/` | Sitios con estado de healthcheck | Supervisor+ |
| PATCH | `/sites/{id}/cameras/` | Actualizar conteo cámaras | Supervisor |
| PATCH | `/sites/{id}/check/` | Marcar revisión | Supervisor |
| PATCH | `/sites/{id}/notes/` | Actualizar notas | Supervisor |
| GET | `/tickets/` | Tickets de soporte | Supervisor+ |
| POST | `/tickets/` | Crear/vincular ticket | Supervisor |
| DELETE | `/tickets/{id}/` | Eliminar ticket | Supervisor |

### 6.7 Admin y Reportes (`/api/v1/admin/`, `/api/v1/reports/`)

| Método | Endpoint | Descripción | Roles |
|--------|----------|-------------|-------|
| GET | `/admin/metrics/` | Dashboard KPIs (sesiones, eventos, covers) | Admin |
| GET | `/admin/alerts/` | Alertas pendientes | Admin |
| GET | `/admin/tables/` | Listar tablas disponibles | Admin |
| GET | `/admin/tables/{name}/` | Datos de tabla con filtros | Admin |
| POST | `/admin/news/` | Crear noticia | Lead Supervisor, Admin |
| GET | `/reports/covers/` | Datos gráfica de covers (7 días) | Lead Supervisor+ |
| GET | `/reports/activity/` | Datos gráfica de actividad (24h) | Lead Supervisor+ |
| GET | `/reports/audit/sessions/` | Auditoría de sesiones | Admin |
| GET | `/reports/audit/events/` | Auditoría de eventos | Admin |

### 6.8 WebSocket Channels (`/ws/`)

| Channel | Propósito | Suscriptores |
|---------|-----------|-------------|
| `ws/stations/` | Estado de estaciones en tiempo real | Supervisores |
| `ws/notifications/{user_id}/` | Notificaciones personales (covers, specials) | Todos |
| `ws/dashboard/` | Métricas en vivo | Admin |
| `ws/news/` | Noticias broadcast | Todos |

---

## 7. MODELOS DJANGO — DISEÑO DETALLADO

> Todos los modelos para tablas existentes usan `managed = False` y `db_constraint = False`.

### 7.1 Core Models

```python
# apps/core/models/user.py
class UserRole(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_user_rol')
    name = models.CharField(max_length=50, db_column='user_rol_name')
    class Meta:
        managed = False
        db_table = 'daily_user_rol'

class User(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_user')
    password = models.CharField(max_length=255, db_column='user_password')
    role = models.ForeignKey(UserRole, db_column='ID_user_rol', db_constraint=False, on_delete=models.DO_NOTHING)
    class Meta:
        managed = False
        db_table = 'daily_users'

class UserName(models.Model):
    """Tabla separada de nombres — mapear o crear proxy."""
    id = models.AutoField(primary_key=True, db_column='ID_user')
    user_name = models.CharField(max_length=100, db_column='user_name')
    class Meta:
        managed = False
        db_table = 'daily_users_names'

# apps/core/models/station.py
class StationInfo(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_station')
    station_number = models.CharField(max_length=20, db_column='station_number')
    class Meta:
        managed = False
        db_table = 'daily_stations_info'

class StationMap(models.Model):
    station = models.OneToOneField(StationInfo, primary_key=True, db_column='station_ID', db_constraint=False, on_delete=models.DO_NOTHING)
    station_user = models.IntegerField(null=True, db_column='station_user')
    is_active = models.IntegerField(null=True, db_column='is_active')
    class Meta:
        managed = False
        db_table = 'daily_stations_map'

# apps/core/models/catalog.py
class Site(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_site')
    group_id = models.IntegerField(db_column='ID_group')
    site_name = models.CharField(max_length=200, db_column='site_name')
    site_dns = models.CharField(max_length=200, null=True, db_column='site_dns')
    site_timezone = models.CharField(max_length=50, null=True, db_column='site_timezone')
    class Meta:
        managed = False
        db_table = 'daily_sites'

class Activity(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_activity')
    act_name = models.CharField(max_length=200, db_column='act_name')
    class Meta:
        managed = False
        db_table = 'daily_activities'
```

### 7.2 Logs Models

```python
# apps/logs/models.py
class DailyEvent(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_event')
    user = models.ForeignKey('core.User', db_column='ID_user', db_constraint=False, on_delete=models.DO_NOTHING)
    site = models.ForeignKey('core.Site', db_column='ID_site', db_constraint=False, on_delete=models.DO_NOTHING)
    activity = models.ForeignKey('core.Activity', db_column='ID_activity', db_constraint=False, on_delete=models.DO_NOTHING)
    event_datetime = models.DateTimeField(db_column='event_datetime')
    event_status = models.CharField(max_length=20, db_column='event_status')  # draft, confirmed, failed
    quantity = models.IntegerField(default=0, db_column='quantity')
    camera = models.CharField(max_length=100, null=True, db_column='camera')
    description = models.TextField(null=True, db_column='description')
    class Meta:
        managed = False
        db_table = 'daily_events'
        ordering = ['-event_datetime']
```

### 7.3 Notifications Models

```python
# apps/notifications/models.py
class Special(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_special')
    event = models.ForeignKey('logs.DailyEvent', db_column='ID_event', db_constraint=False, on_delete=models.DO_NOTHING, null=True)
    user = models.ForeignKey('core.User', db_column='ID_user', db_constraint=False, on_delete=models.DO_NOTHING, related_name='specials_created')
    supervisor = models.ForeignKey('core.User', db_column='ID_supervisor', db_constraint=False, on_delete=models.DO_NOTHING, null=True, related_name='specials_assigned')
    spec_datetime = models.DateTimeField(db_column='spec_datetime')
    spec_status = models.CharField(max_length=20, null=True, db_column='spec_status')  # None, done
    spec_description = models.TextField(null=True, db_column='spec_description')
    spec_marked_at = models.DateTimeField(null=True, db_column='spec_marked_at')
    spec_marked_by = models.IntegerField(null=True, db_column='spec_marked_by')
    class Meta:
        managed = False
        db_table = 'daily_specials'

class News(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_news')
    news_type = models.CharField(max_length=50, db_column='news_type')
    news_info = models.TextField(db_column='news_info')
    news_urgency = models.CharField(max_length=20, db_column='news_urgency')
    news_datetime_in = models.DateTimeField(db_column='news_datetime_in')
    news_datetime_out = models.DateTimeField(null=True, db_column='news_datetime_out')
    active = models.IntegerField(default=1, db_column='active')
    class Meta:
        managed = False
        db_table = 'daily_news'
```

### 7.4 Users/Sessions Models

```python
# apps/users/models.py
class Session(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_sesion')
    user = models.ForeignKey('core.User', db_column='ID_user', db_constraint=False, on_delete=models.DO_NOTHING)
    station = models.ForeignKey('core.StationInfo', db_column='ID_station', db_constraint=False, on_delete=models.DO_NOTHING)
    sesion_in = models.DateTimeField(db_column='sesion_in')
    sesion_out = models.DateTimeField(null=True, db_column='sesion_Out')
    sesion_active = models.IntegerField(default=1, db_column='sesion_active')
    sesion_status = models.IntegerField(default=0, db_column='sesion_status')
    class Meta:
        managed = False
        db_table = 'daily_sesions'

class CoverRequest(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_cover')
    user = models.ForeignKey('core.User', db_column='ID_user', db_constraint=False, on_delete=models.DO_NOTHING)
    cover_time_request = models.DateTimeField(db_column='cover_time_request')
    station = models.ForeignKey('core.StationInfo', db_column='ID_station', db_constraint=False, on_delete=models.DO_NOTHING)
    approved = models.IntegerField(default=0, db_column='approved')
    active = models.IntegerField(default=1, db_column='active')
    class Meta:
        managed = False
        db_table = 'daily_covers_solicitudes'

class CoverCompleted(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_cover_complete')
    user = models.ForeignKey('core.User', db_column='ID_user', db_constraint=False, on_delete=models.DO_NOTHING, related_name='covers_received')
    cover_by = models.ForeignKey('core.User', db_column='ID_user_cover_by', db_constraint=False, on_delete=models.DO_NOTHING, related_name='covers_given')
    cover_in = models.DateTimeField(db_column='cover_in')
    cover_out = models.DateTimeField(null=True, db_column='cover_out')
    class Meta:
        managed = False
        db_table = 'daily_covers_completed'

class Break(models.Model):
    id = models.AutoField(primary_key=True, db_column='ID_break')
    user_covered = models.ForeignKey('core.User', db_column='ID_user_covered', db_constraint=False, on_delete=models.DO_NOTHING, related_name='breaks_received')
    user_covering = models.ForeignKey('core.User', db_column='ID_user_covering', db_constraint=False, on_delete=models.DO_NOTHING, related_name='breaks_given')
    break_datetime = models.DateTimeField(db_column='break_datetime')
    active = models.IntegerField(default=1, db_column='active')
    supervisor = models.ForeignKey('core.User', db_column='ID_supervisor', db_constraint=False, on_delete=models.DO_NOTHING, null=True, related_name='breaks_supervised')
    break_creation = models.DateTimeField(null=True, db_column='break_creation')
    class Meta:
        managed = False
        db_table = 'daily_breaks'
```

### 7.5 Audit Models (NUEVA — managed = True)

```python
# apps/audit/models.py
class AuditLog(models.Model):
    """Tabla nueva para auditoría centralizada. managed=True."""
    id = models.BigAutoField(primary_key=True)
    user_id = models.IntegerField()
    session_id = models.IntegerField(null=True)
    action = models.CharField(max_length=100)  # LOGIN, LOGOUT, CREATE_EVENT, etc.
    resource = models.CharField(max_length=100)  # events, specials, covers, etc.
    resource_id = models.IntegerField(null=True)
    detail = models.JSONField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=500, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        managed = True
        db_table = 'daily_audit_log'
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
```

---

## 8. REGLAS DE IMPLEMENTACIÓN

### 8.1 Reglas Técnicas (Backend Engineer)

- **Tipado completo** en funciones de servicio y serializers
- **Manejo explícito de errores** con excepciones custom (`apps/core/exceptions.py`)
- **Validaciones en capa de dominio** (services), no solo en serializers
- **`transaction.atomic()`** para operaciones multi-tabla (covers, breaks, login/logout)
- **Consultas optimizadas**: `select_related()`, `prefetch_related()`, evitar N+1
- **Índices explícitos** cuando se agreguen campos nuevos
- **NUNCA** usar `Model.objects` directamente en views — siempre vía services

### 8.2 Estándares de Código

- Métodos pequeños y atómicos
- Funciones puras cuando sea posible
- Sin side-effects ocultos
- No duplicar lógica entre apps

### 8.3 Seguridad

- Variables sensibles en `.env` (NUNCA en código)
- Validar permisos explícitamente en cada view
- Sanitización de inputs que vayan a raw SQL (si es necesario)
- Rate limiting en endpoints de auth
- CORS configurado por ambiente

### 8.4 Prohibiciones

- NO hardcodear IPs, contraseñas, puertos en código
- NO introducir dependencias sin justificación
- NO crear lógica fuera del patrón services/views/serializers
- NO modificar tablas existentes con `managed = True` (excepto tablas nuevas)
- NO usar `raw()` o `extra()` excepto para queries complejas sin equivalente ORM

---

## 9. PLAN DE EJECUCIÓN POR FASES

### Fase 1: Scaffolding y Core (Fundación)
1. Crear proyecto Django con `django-admin startproject config .`
2. Configurar settings split (base/dev/prod/test)
3. Configurar conexión MySQL existente
4. Crear `apps/core/` con modelos base (User, Role, Station, Site, Activity)
5. `python manage.py inspectdb` para validar mapeo de tablas
6. Configurar `django-environ` y `.env`
7. Crear permisos custom (IsOperator, IsSupervisor, IsAdmin, IsLeadSupervisor)
8. Configurar DRF defaults (pagination, auth, renderers)

### Fase 2: Autenticación y Usuarios
1. Custom auth backend que valide contra `daily_users`
2. JWT con `simplejwt`
3. Login endpoint (crear sesión BD + JWT)
4. Logout endpoint (cerrar sesión BD + liberar estación + blacklist token)
5. Endpoint `/me/` con perfil y status
6. Endpoint cambio de status

### Fase 3: Daily Events (Módulo Principal)
1. Modelos: DailyEvent con relaciones
2. Serializers: lectura con nested, escritura con PKs
3. Services: create_event (draft→confirmed flow), update, filtrado
4. ViewSet con filtros (user, site, date_range, activity, status)
5. Endpoint `/my-daily/` para turno actual

### Fase 4: Specials y Notifications
1. Modelos: Special, News
2. Services: auto_assign_supervisor (lógica de rangos + manual), transfer
3. ViewSet con acciones custom (assign, mark_done, transfer)
4. News CRUD

### Fase 5: Covers y Breaks
1. Modelos: CoverRequest, CoverCompleted, Break
2. Services: flujo completo request→approve→execute→exit
3. Services: break programado→iniciar→cover automático
4. ViewSets con state machine actions

### Fase 6: Sesiones y Estaciones
1. Modelos: Session, StationMap, SupervisorStationSelection, SupervisorStationRange
2. Services: asignación manual, rangos automáticos, detección unsupervised
3. ViewSets con endpoints de mapa y asignación

### Fase 7: Admin, Reportes y Healthcheck
1. Dashboard metrics endpoint (portando `get_dashboard_metrics()`)
2. Reportes de covers y actividad (gráficas)
3. Auditoría de sesiones y eventos
4. Healthcheck sites y tickets
5. Admin CRUD genérico de tablas

### Fase 8: Real-time y Async
1. Django Channels setup con Redis
2. WebSocket consumers (stations, notifications, dashboard)
3. Celery setup para healthcheck polling y limpieza
4. Migrar lógica de polling a push

### Fase 9: Auditoría Centralizada
1. Modelo AuditLog (managed=True, tabla nueva)
2. Middleware de auditoría automática
3. Endpoints de consulta de audit trail

### Fase 10: Docker y Deploy
1. Dockerfile multi-stage
2. docker-compose (django, celery, redis, nginx)
3. CI/CD pipeline
4. Configuración de producción (gunicorn, static files)

---

## 10. DECISIONES TÉCNICAS CLAVE

### ¿Por qué `managed = False`?
La base de datos es compartida con la app de escritorio que seguirá operando en paralelo. Django NO debe alterar el schema existente. Solo tablas nuevas (como `daily_audit_log`) serán `managed = True`.

### ¿Por qué `db_constraint = False` en ForeignKeys?
La BD existente no tiene FK constraints declaradas. Declarar constraints en Django causaría errores en `migrate` al intentar crear constraints que no existen.

### ¿Por qué JWT y no Session Auth?
La API servirá a un frontend SPA (Single Page Application). JWT es stateless, funciona bien con CORS, y permite refresh tokens sin round-trips al servidor.

### ¿Por qué Redis para cache y channels?
Reemplaza el cache en memoria (no compartible entre workers/procesos) y sirve como broker para Celery y backend para Channels, unificando la infraestructura.

### ¿Por qué Celery?
El healthcheck module hace polling a APIs externas (Service Desk). Esto debe ejecutarse en background sin bloquear request/response cycles.

### ¿Por qué `mysqlclient` en vez de `pymysql`?
`mysqlclient` es el driver MySQL recomendado por Django, ~10x más rápido que pymysql (es binding C). El proyecto de escritorio usa pymysql porque es pure-Python y más fácil de empaquetar en .exe.

---

## 11. VARIABLES DE ENTORNO REQUERIDAS

```env
# .env (NUNCA en repositorio)
SECRET_KEY=django-insecure-generate-a-real-one
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=sig_dailylogs
DB_USER=<usuario>
DB_PASSWORD=<contraseña>
DB_HOST=72.167.56.142
DB_PORT=3306

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
```

---

## 12. GLOSARIO DEL DOMINIO

| Término | Significado |
|---------|-------------|
| **Daily Event** | Registro de actividad de monitoreo (operador observa sitio, reporta evento) |
| **Special** | Evento que requiere atención de supervisor (escalamiento) |
| **Cover** | Un operador reemplaza a otro temporalmente en su estación |
| **Cover Request (Solicitud)** | Petición formal de cover con hora programada |
| **Cover Completed** | Registro de cover ejecutado (cover_in, cover_out) |
| **Break** | Descanso programado que requiere cover |
| **Station** | Puesto de trabajo físico con número identificador |
| **Station Map** | Relación estación ↔ usuario activo |
| **Supervisor Range** | Rango de estaciones asignadas automáticamente a un supervisor |
| **Healthcheck (HC)** | Verificación del estado de cámaras/sitios monitoreados |
| **Session** | Periodo login→logout de un usuario en una estación |
| **Status** | Estado del operador: 0=offline, 1=activo, 2=lista (disponible para cover) |
| **Site** | Ubicación física monitoreada (con timezone propio) |
| **Activity** | Tipo de evento (Start Shift, Test Call, Alarm, etc.) |
| **News** | Anuncios/alertas internas visibles para todos los usuarios |
| **Draft/Confirmed** | Flujo de eventos: se crean como draft y se confirman al completar |

---

## 13. CONTEXTO PARA EL AGENTE IA

### Cuando se te pida implementar un módulo:
1. **Lee este README completo** antes de escribir código
2. **Consulta la sección 5** para mapear funciones existentes
3. **Respeta la sección 8** para reglas y prohibiciones
4. **Sigue la sección 4.3** para convenciones de código
5. **Usa la sección 7** como referencia para modelos
6. **Valida permisos** según la sección 3.2

### Cuando se te pida una consulta de BD compleja:
1. Revisa la sección 2 para nombres exactos de tablas y columnas
2. Usa `db_column` en los modelos para mapear correctamente
3. Recuerda: NO hay FK en la BD, usa `db_constraint=False`

### Cuando se te pida agregar un endpoint:
1. Revisa si ya existe en la sección 6
2. Crea: model → serializer → service → view → url (en ese orden)
3. Agrega permisos explícitos
4. Documenta en el serializer para drf-spectacular

### Cuando detectes inconsistencias:
- Tablas legacy vs modernas: prioriza siempre las tablas con prefijo `daily_`
- Si un modelo del proyecto_app usa tabla legacy, mapea a la equivalente moderna
- Si no existe equivalente moderna, documenta y pregunta

---

> **Última actualización:** 2026-04-08
> **Mantenido por:** Equipo de desarrollo Daily Log — SIG Systems, Inc.
