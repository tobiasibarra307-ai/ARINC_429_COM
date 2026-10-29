# ARINC-429: envíos locales

La aplicación guarda los envíos en MySQL local. La web y la consola usan la misma tabla `arinc429.envios`.

## Preparar MySQL

Se necesita MySQL Server en ejecución. En Ubuntu, crea la base de datos y una cuenta limitada al usuario Linux actual. Reemplaza `USUARIO_LINUX` por el resultado de `whoami`:

```sql
CREATE DATABASE IF NOT EXISTS arinc429 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'USUARIO_LINUX'@'localhost' IDENTIFIED WITH auth_socket;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX ON arinc429.* TO 'USUARIO_LINUX'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON ARINC_429.* TO 'USUARIO_LINUX'@'localhost';
```

La tabla de envíos y sus columnas se crean automáticamente en una instalación nueva. El CRUD web consulta y modifica los instrumentos existentes en `ARINC_429.instrumentos`; no crea una segunda tabla de instrumentos. Si ya existía la tabla antigua de envíos, MySQL requiere permisos administrativos para esta migración de una sola vez:

```sql
ALTER TABLE arinc429.envios
	ADD COLUMN label_octal VARCHAR(3) NOT NULL DEFAULT '000',
	ADD COLUMN sdi TINYINT UNSIGNED NOT NULL DEFAULT 0,
	ADD COLUMN dato_raw INT UNSIGNED NOT NULL DEFAULT 0,
	ADD COLUMN ssm TINYINT UNSIGNED NOT NULL DEFAULT 0,
	ADD COLUMN arinc429_word BIGINT UNSIGNED NOT NULL DEFAULT 2147483648,
	ADD COLUMN arinc429_hex CHAR(10) NOT NULL DEFAULT '0x80000000',
	ADD COLUMN arinc429_bin CHAR(32) NOT NULL DEFAULT '10000000000000000000000000000000',
	ADD COLUMN arinc429_bytes_hex CHAR(11) NOT NULL DEFAULT '80 00 00 00',
	ADD COLUMN salida_modo VARCHAR(20) NOT NULL DEFAULT 'simulacion';
```

Ejecuta ese `ALTER TABLE` solo si la tabla anterior aún no tiene esas columnas. La autenticación `auth_socket` permite usarla localmente con el mismo usuario Linux, sin poner contraseñas en el código.

## Palabra ARINC 429

Cada envío recibe un instrumento activo del inventario `ARINC_429.instrumentos`, su número de serie, si es analógico o digital, una medición física y una palabra ARINC completa de 32 bits. El nombre y el ID del instrumento se guardan en el envío; los límites de medición se definen en el formulario para cada envío.

| Instrumento | Mínimo | Máximo | Unidad |
| --- | ---: | ---: | --- |
| Velocímetro (velocidad indicada) | 0 | 600 | kt |
| Altímetro | -1000 | 60000 | ft |
| Brújula magnética (rumbo) | 0 | 360 | grados |
| Indicador de velocidad vertical | -6000 | 6000 | ft/min |
| Indicador de actitud (eje angular) | -90 | 90 | grados |
| Temperatura exterior | -80 | 60 | °C |

Los rangos reales dependen del modelo instalado y deben verificarse en su manual. Los instrumentos del inventario se administran desde la misma página de envíos, y solo los que están en estado `activo` pueden seleccionarse.

`dato_raw` es un entero entre `0` y `4294967295` que representa la palabra completa. Se guarda exactamente ese valor; la aplicación calcula hexadecimal, binario y cuatro bytes, y muestra los segmentos de paridad, SSM, datos, SDI y label. No convierte automáticamente la medición física en bits ni vuelve a empaquetar los campos: ingresa una palabra ya preparada según la especificación ARINC del instrumento.

Al iniciar, la aplicación crea automáticamente las tablas complementarias `envios_metadata` y `envios_medicion` para guardar serie/tipo y perfil/medición/rango sin alterar la tabla `envios`; los registros anteriores aparecen con esos datos sin especificar. Esto usa los permisos `CREATE` ya concedidos y no requiere una migración manual para esos campos. `dato_raw` ya es `INT UNSIGNED`, con capacidad para 32 bits.

Los límites mínimo y máximo de la web restringen el valor que se puede enviar desde el formulario. La base existente no requiere migración: `dato_raw` ya es `INT UNSIGNED`, con capacidad para 32 bits.

Todavía no se transmite a un bus físico: los registros quedan marcados `simulacion`. Los cuatro bytes hexadecimales son una representación de la palabra, no una trama lista para enviar por UART. Hace falta un transmisor/adaptador ARINC 429 compatible; un puerto USB-serial común no genera niveles eléctricos ARINC 429.

### Recibir palabras desde un Arduino por USB/serial

Si el Arduino ya obtiene o construye la palabra de 32 bits, el puente `serial_bridge.py` lee una palabra por línea y la guarda como envío digital personalizado en esta aplicación. Acepta decimal, hexadecimal (`0x1234ABCD`), binario con prefijo (`0b...`) o una cadena binaria de exactamente 32 bits. El puerto USB del Arduino solo transporta esos datos entre Arduino y computadora; no es una interfaz eléctrica ARINC 429.

En el Arduino, envía cada palabra como una línea terminada en salto de línea y usa la misma velocidad en ambos lados, por ejemplo:

```cpp
void setup() {
	Serial.begin(115200);
}

void loop() {
	uint32_t palabra = 0x80000000UL; // Reemplazar con la palabra calculada o recibida
	Serial.println(palabra);         // Decimal, una palabra por línea
	delay(1000);
}
```

Con la web ejecutándose, instala dependencias y localiza el puerto del Arduino:

```bash
cd /ruta/al/ARINC_429_COM
.venv/bin/pip install -r requirements.txt
ls /dev/ttyACM* /dev/ttyUSB*
```

Inicia el puente usando el dispositivo que corresponda:

```bash
.venv/bin/python serial_bridge.py --port /dev/ttyACM0 --baud 115200 --url http://127.0.0.1:8001
```

Reemplaza `/dev/ttyACM0` por el puerto que encontraste. El puente registra cada línea válida en MySQL y muestra el ID del envío; `Ctrl+C` lo detiene. Si el Arduino envía por primera vez sin datos, verifica que esté transmitiendo líneas ASCII terminadas en `\\n` y que coincida la velocidad en baudios. Este flujo no lee directamente un bus ARINC 429; para eso se requiere un transceptor/adaptador compatible.

El botón `Tono` reproduce por la salida de audio del equipo un tono proporcional al valor decimal de la palabra. Es una representación audible, no una salida de tensión DC calibrada. Para producir tensión con unidades/rango garantizados se requiere un DAC y definir voltaje mínimo/máximo, aislamiento y calibración.

## Instalar y ejecutar

Desde esta carpeta:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

La página queda en <http://127.0.0.1:8000>. Si ese puerto está ocupado, inicia con `PORT=8001 .venv/bin/python server.py`.

## Administrar desde cualquier terminal

El comando `envios` del proyecto puede ejecutarse desde esta carpeta:

```bash
./envios listar
./envios vigilar
./envios instrumentos
./envios crear --instrumento "Brújula magnética" --numero-serie BM-2048 --tipo-instrumento analogico --dato-raw 2147483648
./envios ver 1
./envios actualizar 1 --instrumento Altímetro --numero-serie ALT-8 --tipo-instrumento digital --dato-raw 4294967295
./envios eliminar 1
```

El borrado pide confirmación; usa `eliminar 1 --confirmar` para automatizarlo. `envios --help` muestra todos los comandos.

`envios vigilar` muestra en Konsole una tabla detallada con instrumento, serie, tipo, medición, rango, campos ARINC, segmentos de bits, bytes, modo y fecha. Se actualiza cada segundo desde la misma base MySQL que usa la web; pulsa `Ctrl+C` para salir. Puedes cambiar el intervalo, por ejemplo, `envios vigilar --intervalo 0.5`.

También puedes inspeccionar MySQL directamente desde Konsole con el cliente SQL:

```bash
mysql
SHOW DATABASES;
USE arinc429;
SHOW TABLES;
SELECT e.id, e.instrumento_nombre,
	   COALESCE(NULLIF(m.numero_serie, ''), 'sin serie') AS numero_serie,
	   COALESCE(m.tipo_instrumento, 'no especificado') AS tipo_instrumento,
	   e.valor, e.label_octal, e.sdi, e.dato_raw, e.ssm, e.arinc429_word,
	   e.arinc429_hex, e.arinc429_bin, e.arinc429_bytes_hex,
	   e.salida_modo, e.creado_en
FROM envios AS e
LEFT JOIN envios_metadata AS m ON m.envio_id = e.id
ORDER BY e.id DESC;
EXIT;
```

Para refrescar esa consulta automáticamente cada segundo desde la shell:

```bash
watch -n 1 'mysql --table arinc429 -e "SELECT e.id, e.instrumento_nombre, COALESCE(NULLIF(m.numero_serie, \"\"), \"sin serie\") AS numero_serie, COALESCE(m.tipo_instrumento, \"no especificado\") AS tipo_instrumento, e.valor, e.label_octal, e.sdi, e.dato_raw, e.ssm, e.arinc429_word, e.arinc429_hex, e.arinc429_bin, e.arinc429_bytes_hex, e.salida_modo, e.creado_en FROM envios AS e LEFT JOIN envios_metadata AS m ON m.envio_id = e.id ORDER BY e.id DESC"'
```

## Configuración opcional

Por defecto usa el socket local `/var/run/mysqld/mysqld.sock`, la cuenta del usuario Linux actual y la base `arinc429` para envíos. El inventario se lee y modifica en `ARINC_429`. Para otro servidor, define `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DATABASE` en el entorno antes de iniciar el servidor o la CLI. La aplicación web se enlaza solo a `127.0.0.1`.