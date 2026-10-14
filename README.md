# GestuVoz — Backend

API REST del **Sistema aumentativo y alternativo de comunicación basado en
machine learning para apoyar la comunicación no verbal de niños con TEA en Lima
Metropolitana**.

Recibe los datos que la app móvil sincroniza, los guarda en **Cloud Firestore**
y genera los reportes de uso. La autenticación de padres o tutores la hace
**Firebase Authentication**.

```
App móvil (Flutter) ──login──► Firebase Authentication
        │                              │ token
        └──── HTTPS / REST + token ───►│
                                       ▼
                         Backend Django (este repositorio)
                                       │ Firebase Admin SDK
                                       ▼
                                Cloud Firestore
```

---

## Tabla de contenidos

- [Tecnologías](#tecnologías)
- [Datos en Cloud Firestore](#datos-en-cloud-firestore)
- [Reglas de negocio](#reglas-de-negocio)
- [API](#api)
- [Instalación local](#instalación-local)
- [Pruebas](#pruebas)
- [Despliegue en Render](#despliegue-en-render)
- [Seguridad](#seguridad)

---

## Tecnologías

| Componente | Tecnología |
|------------|------------|
| Lenguaje y framework | Python + Django + Django REST Framework |
| Base de datos | Cloud Firestore (única base de datos; Django no usa SQL) |
| Autenticación | Firebase Authentication (verificación del token con Firebase Admin SDK) |
| Servidor | Gunicorn en Render |

---

## Datos en Cloud Firestore

| Colección | Contenido |
|-----------|-----------|
| `perfiles` | Perfil del niño: nivel de apoyo, estado, `preferencias_de_comunicacion` (pictogramas visibles y su orden, tamaño, gestos activados y habilitados, alto contraste), `id_nino`, `id_tutor` |
| `ninos` | Nombre, fecha de nacimiento y género del niño |
| `pictogramas` | Pictogramas personalizados del tutor (nombre, mensaje, categoría, `referencia_imagen`) |
| `intenciones_comunicativas` | Catálogo de intenciones asociadas a los gestos |
| `configuraciones_voz` | Idioma, tipo de voz, velocidad, volumen y voz activada de cada perfil |
| `consentimientos` | Estado del consentimiento y fechas de registro y retiro |
| `interacciones` | Historial: fecha y hora, detalle, perfil, gesto, intención y pictograma |

- El **tutor** es el usuario de Firebase Authentication; su UID se guarda en
  `id_tutor`.
- Los **gestos, categorías y pictogramas iniciales** vienen dentro de la app y
  tienen el mismo identificador en todos los teléfonos, así que no se suben.
  Convención de identificadores:

  | Elemento | Identificador |
  |----------|---------------|
  | Pictograma inicial | `base-<id local>` (por ejemplo `base-12`) |
  | Pictograma personalizado, perfil, niño, interacción | UUID generado por la app |
  | Gesto | `gesto-<id local>` |
  | Intención | `intencion-<id local>` |

- Las imágenes de los pictogramas personalizados se guardarán en Cloud Storage
  cuando se active; mientras tanto `referencia_imagen` queda vacía y la imagen
  permanece en el teléfono.

---

## Reglas de negocio

- **Acceso solo a lo propio:** cada tutor ve y modifica únicamente sus
  perfiles. Si intenta acceder a uno ajeno, recibe "no encontrado".
- **Consentimiento:** la decisión de consentimiento siempre puede
  registrarse. Si no está otorgado o fue retirado, se rechazan los datos de ese
  perfil (`403 consentimiento_requerido`) y los datos ya guardados no se
  borran.
- **Gana el último cambio:** cada documento lleva `actualizado_en`. Si la app
  envía una versión más antigua que la guardada, recibe `409` junto con la
  versión actual.
- **Sincronización sin duplicados:** las interacciones se envían por lotes y
  cada una se crea una sola vez, aunque se reenvíe.
- **Eliminar un perfil** borra su niño, consentimiento, configuración de voz e
  interacciones.
- **Reportes descriptivos:** resumen de uso sin interpretaciones clínicas,
  calculado en hora de Lima.

---

## API

Base: `/api/v1/`. Todas las rutas, salvo `salud`, requieren:

```
Authorization: Bearer <ID token de Firebase>
```

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `salud` | Estado del servicio (sin autenticación) |
| GET | `yo` | UID y correo del tutor autenticado |
| GET | `perfiles` | Perfiles del tutor, cada uno con sus datos del niño |
| GET · PUT · DELETE | `perfiles/{id_perfil}` | Consultar, crear o actualizar (incluye `nino`), eliminar |
| GET · PUT | `perfiles/{id_perfil}/consentimiento` | Decisión de consentimiento |
| GET · PUT | `perfiles/{id_perfil}/configuracion-voz` | Configuración de voz |
| GET · POST | `perfiles/{id_perfil}/interacciones` | Historial (`?desde=AAAA-MM-DD&hasta=AAAA-MM-DD`) · envío por lote |
| GET | `perfiles/{id_perfil}/interacciones/{id}` | Detalle de una interacción |
| GET | `perfiles/{id_perfil}/reportes` | Resumen, actividad semanal y más frecuentes (`?desde&hasta`) |
| GET | `pictogramas` | Pictogramas personalizados del tutor |
| PUT · DELETE | `pictogramas/{id_pictograma}` | Crear o actualizar (`?id_perfil=...`) · eliminar |
| GET | `intenciones` | Catálogo de intenciones comunicativas |

Orden recomendado al crear un perfil desde la app: **1)** `PUT .../consentimiento`
y, si fue otorgado, **2)** `PUT perfiles/{id}`, **3)** `PUT .../configuracion-voz`.

Errores con formato uniforme:

```json
{ "error": { "codigo": "consentimiento_requerido", "detalle": "..." } }
```

---

## Instalación local

Requisitos: Python 3.12 o superior.

```bash
git clone https://github.com/GestuVoz-TP1/Backend.git
cd Backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env
```

En `.env`:

- `DJANGO_SECRET_KEY`: una cadena aleatoria larga.
- `FIREBASE_CREDENTIALS_FILE`: ruta al JSON de la cuenta de servicio de
  Firebase (Configuración del proyecto → Cuentas de servicio → Generar nueva
  clave privada), guardado **fuera** del repositorio.

Cargar el catálogo de intenciones en Firestore (una sola vez):

```bash
python manage.py cargar_catalogo
```

Iniciar el servidor:

```bash
python manage.py runserver 0.0.0.0:8000
```

Desde el emulador de Android, la app accede al servidor local en
`http://10.0.2.2:8000/api/v1/`.

---

## Pruebas

```bash
python manage.py test api
```

Las pruebas usan un Firestore en memoria y tokens de prueba; no necesitan
credenciales ni conexión. Cubren autenticación, acceso solo a lo propio,
consentimiento, "gana el último cambio", validaciones, sincronización sin
duplicados, filtros por fecha, reportes y eliminación en cascada.

---

## Despliegue en Render

El archivo `render.yaml` define el servicio. En el panel de Render:

1. **New → Blueprint** y seleccionar este repositorio.
2. En la variable `FIREBASE_CREDENTIALS_JSON`, pegar el **contenido** del JSON
   de la cuenta de servicio.
3. Desplegar y comprobar `https://<servicio>.onrender.com/api/v1/salud`.

En el plan gratuito el servicio se suspende tras 15 minutos sin uso y la
primera petición tarda alrededor de un minuto.

---

## Seguridad

- La credencial de Firebase **nunca** se sube al repositorio (`.gitignore`) y
  se carga desde variables de entorno.
- En producción: HTTPS obligatorio, HSTS y `DEBUG` desactivado.
- `firestore.rules` niega todo acceso directo a Firestore desde clientes; solo
  el backend accede con la cuenta de servicio.
- El token de Firebase se verifica en cada petición, incluida su revocación.

---

Proyecto de Taller de Proyecto · Ingeniería de Software · Universidad Peruana
de Ciencias Aplicadas (UPC).
