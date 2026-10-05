# ZAFIRAH Gestión

Sistema administrativo web para ZAFIRAH: stock, compras, ventas, producción por recetas, costos, gastos y rentabilidad.

## Qué incluye

- Usuario administrador protegido por contraseña.
- Dashboard mensual: ventas, ganancia bruta, gastos y ganancia neta.
- Productos terminados con SKU, categoría, costo, precio, stock y mínimo.
- Insumos/materias primas con unidad, costo medio, stock y mínimo.
- Recetas/BOM por producto.
- Compras multiítem: aumentan stock y recalculan costo medio de insumos.
- Producción: descuenta automáticamente los insumos de la receta, calcula costo del lote y aumenta el stock terminado.
- Ventas multiítem: controla stock, descuenta unidades y congela el costo utilizado para calcular COGS y ganancia.
- Gastos operativos.
- Proveedores y clientes.
- Informes por rango de fechas y rentabilidad por producto.
- Auditoría de todos los movimientos de inventario.
- Anulación de compras, ventas y producciones con reversión de stock.
- Exportación de ventas y stock a CSV.
- Backup descargable de la base completa.
- Interfaz responsive + PWA instalable en celular.

## Windows: instalación y uso

1. Descomprimí la carpeta en un lugar fijo, por ejemplo `C:\ZAFIRAH_Gestion`.
2. Asegurate de tener **Python 3.11 o superior** instalado desde python.org y marcado `Add Python to PATH`.
3. Hacé doble clic en `INICIAR_ZAFIRAH.bat`.
4. La primera ejecución instala automáticamente las dependencias y abre `http://127.0.0.1:8000`.
5. Creá tu usuario administrador y una contraseña de al menos 8 caracteres.
6. Podés marcar **Cargar el catálogo inicial de ZAFIRAH** para crear los jabones, velas y tabletas conocidos; después completá precios y costos.
7. No cierres la ventana negra mientras estés usando el sistema.

La base de datos queda en `data/zafirah.db`.

## Orden recomendado de carga inicial

1. Insumos y materias primas.
2. Stock inicial y costos de esos insumos.
3. Productos terminados y precios de venta.
4. Recetas de cada jabón/vela/tableta.
5. Stock inicial de productos terminados si ya tenés mercadería fabricada.
6. Proveedores y clientes frecuentes.
7. Desde ese punto registrar normalmente compras, producción, ventas y gastos.

## Criterio de ganancias

- **Ventas** = ingresos por ventas activas.
- **Costo vendido (COGS)** = cantidad vendida × costo unitario congelado en el momento de la venta.
- **Ganancia bruta** = ventas − costo vendido.
- **Ganancia neta** = ganancia bruta − gastos operativos.

Las compras de materia prima no se restan nuevamente como gasto en la ganancia neta porque su costo pasa al producto mediante producción y luego a COGS cuando se vende. Esto evita duplicar costos.

## Copias de seguridad

En `Más → Backup` podés descargar una copia completa. Es recomendable hacerlo periódicamente y guardar el archivo fuera de la computadora principal.

## Uso desde otro dispositivo de la misma red

Con la PC encendida y el sistema ejecutándose, obtené la IP local de la PC (por ejemplo `192.168.1.50`) y desde el celular abrí `http://192.168.1.50:8000`. Windows puede pedir permiso para permitir Python/Uvicorn en la red privada.

## Publicación online

El proyecto incluye `Dockerfile` y puede desplegarse en un servidor. Para una publicación pública permanente conviene migrar la base SQLite a PostgreSQL/Supabase y configurar HTTPS, dominio y backups remotos. El sistema administrativo debe quedar protegido y separado de la web pública.

## Seguridad

- La contraseña se almacena con `scrypt` y sal aleatoria; nunca se guarda en texto plano.
- Los formularios tienen protección CSRF.
- El secreto de sesión se genera automáticamente en `data/.session_secret`.
- Antes de publicar en Internet, usar HTTPS y una configuración de despliegue dedicada.
