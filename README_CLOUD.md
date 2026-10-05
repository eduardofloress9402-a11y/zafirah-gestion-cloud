# ZAFIRAH Gestión — versión Cloud

Esta versión funciona de dos formas:

- **Local**: si no existe `DATABASE_URL`, usa SQLite en `data/zafirah.db`.
- **Cloud**: si existe `DATABASE_URL`, usa PostgreSQL (por ejemplo Supabase).

## Variables de entorno para producción

- `DATABASE_URL`: cadena de conexión PostgreSQL.
- `ZAFIRAH_SECRET`: valor aleatorio largo para firmar sesiones.
- `COOKIE_SECURE=1`: obliga a que la cookie de sesión viaje solo por HTTPS.

## Inicio

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Render

El proyecto incluye `render.yaml` y `Dockerfile`.

1. Subir esta carpeta a un repositorio de GitHub.
2. Crear un proyecto PostgreSQL en Supabase.
3. Copiar la cadena de conexión de Supabase.
4. Crear un Web Service en Render desde el repositorio.
5. Configurar `DATABASE_URL` con la cadena de Supabase.
6. Configurar `COOKIE_SECURE=1` y generar `ZAFIRAH_SECRET`.
7. Desplegar.
8. Abrir la URL pública y crear el usuario administrador desde `/setup`.

## Backup

`/backup` genera un ZIP con todos los datos en JSON y funciona tanto con SQLite como con PostgreSQL.
