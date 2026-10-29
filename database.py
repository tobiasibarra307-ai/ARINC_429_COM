import getpass
import os
from datetime import datetime, timezone

from arinc429 import decodificar_palabra


DATABASE_NAME = os.environ.get("MYSQL_DATABASE", "arinc429")


def conectar(base_datos=DATABASE_NAME):
    try:
        import pymysql
    except ImportError as error:
        raise RuntimeError(
            "Falta PyMySQL. Instálalo con: python3 -m pip install -r requirements.txt"
        ) from error

    configuracion = {
        "user": os.environ.get("MYSQL_USER", os.environ.get("DB_USER", getpass.getuser())),
        "password": os.environ.get("MYSQL_PASSWORD", os.environ.get("DB_PASSWORD", "")),
        "database": base_datos,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 5,
    }
    host = os.environ.get("MYSQL_HOST", os.environ.get("DB_HOST"))
    if host:
        configuracion["host"] = host
        configuracion["port"] = int(os.environ.get("MYSQL_PORT", os.environ.get("DB_PORT", "3306")))
    else:
        configuracion["unix_socket"] = os.environ.get(
            "MYSQL_SOCKET", "/var/run/mysqld/mysqld.sock"
        )
    return pymysql.connect(**configuracion)


def listar_instrumentos():
    conexion = conectar("ARINC_429")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """SELECT id, nombre, modelo, fabricante, tipo, descripcion, estado,
                          CAST(creado_en AS CHAR) AS creado_en,
                          CAST(actualizado_en AS CHAR) AS actualizado_en
                   FROM instrumentos ORDER BY id DESC"""
            )
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_instrumento(instrumento_id):
    conexion = conectar("ARINC_429")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """SELECT id, nombre, modelo, fabricante, tipo, descripcion, estado,
                          CAST(creado_en AS CHAR) AS creado_en,
                          CAST(actualizado_en AS CHAR) AS actualizado_en
                   FROM instrumentos WHERE id = %s""",
                (instrumento_id,),
            )
            return cursor.fetchone()
    finally:
        conexion.close()


def crear_instrumento(datos):
    conexion = conectar("ARINC_429")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """INSERT INTO instrumentos (nombre, modelo, fabricante, tipo, descripcion, estado)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (datos["nombre"], datos["modelo"], datos["fabricante"], datos["tipo"],
                 datos["descripcion"], datos["estado"]),
            )
            instrumento_id = cursor.lastrowid
        conexion.commit()
        return obtener_instrumento(instrumento_id)
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def actualizar_instrumento(instrumento_id, datos):
    conexion = conectar("ARINC_429")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """UPDATE instrumentos
                   SET nombre = %s, modelo = %s, fabricante = %s, tipo = %s,
                       descripcion = %s, estado = %s
                   WHERE id = %s""",
                (datos["nombre"], datos["modelo"], datos["fabricante"], datos["tipo"],
                 datos["descripcion"], datos["estado"], instrumento_id),
            )
            encontrado = cursor.rowcount > 0
            if not encontrado:
                cursor.execute("SELECT id FROM instrumentos WHERE id = %s", (instrumento_id,))
                encontrado = cursor.fetchone() is not None
        conexion.commit()
        return obtener_instrumento(instrumento_id) if encontrado else None
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def eliminar_instrumento(instrumento_id):
    conexion = conectar("ARINC_429")
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM instrumentos WHERE id = %s", (instrumento_id,))
            eliminado = cursor.rowcount > 0
        conexion.commit()
        return eliminado
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def inicializar_base_de_datos():
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS envios (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    instrumento_id VARCHAR(32) NOT NULL,
                    instrumento_nombre VARCHAR(120) NOT NULL,
                    valor VARCHAR(500) NOT NULL,
                    label_octal VARCHAR(3) NOT NULL DEFAULT '000',
                    sdi TINYINT UNSIGNED NOT NULL DEFAULT 0,
                    dato_raw INT UNSIGNED NOT NULL DEFAULT 0,
                    ssm TINYINT UNSIGNED NOT NULL DEFAULT 0,
                    arinc429_word BIGINT UNSIGNED NOT NULL DEFAULT 2147483648,
                    arinc429_hex CHAR(10) NOT NULL DEFAULT '0x80000000',
                    arinc429_bin CHAR(32) NOT NULL DEFAULT '10000000000000000000000000000000',
                    arinc429_bytes_hex CHAR(11) NOT NULL DEFAULT '80 00 00 00',
                    salida_modo VARCHAR(20) NOT NULL DEFAULT 'simulacion',
                    creado_en VARCHAR(32) NOT NULL,
                    INDEX idx_envios_creado_en (creado_en)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cursor.execute("SHOW COLUMNS FROM envios")
            columnas = {columna["Field"] for columna in cursor.fetchall()}
            nuevas_columnas = {
                "label_octal": "VARCHAR(3) NOT NULL DEFAULT '000'",
                "sdi": "TINYINT UNSIGNED NOT NULL DEFAULT 0",
                "dato_raw": "INT UNSIGNED NOT NULL DEFAULT 0",
                "ssm": "TINYINT UNSIGNED NOT NULL DEFAULT 0",
                "arinc429_word": "BIGINT UNSIGNED NOT NULL DEFAULT 2147483648",
                "arinc429_hex": "CHAR(10) NOT NULL DEFAULT '0x80000000'",
                "arinc429_bin": "CHAR(32) NOT NULL DEFAULT '10000000000000000000000000000000'",
                "arinc429_bytes_hex": "CHAR(11) NOT NULL DEFAULT '80 00 00 00'",
                "salida_modo": "VARCHAR(20) NOT NULL DEFAULT 'simulacion'",
            }
            for nombre, tipo in nuevas_columnas.items():
                if nombre not in columnas:
                    cursor.execute(f"ALTER TABLE envios ADD COLUMN {nombre} {tipo}")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS envios_metadata (
                    envio_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
                    numero_serie VARCHAR(120) NOT NULL DEFAULT '',
                    tipo_instrumento VARCHAR(20) NOT NULL DEFAULT 'no especificado'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS envios_medicion (
                    envio_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
                    perfil_id VARCHAR(40) NOT NULL DEFAULT 'personalizado',
                    valor_medicion DECIMAL(30, 10) NULL,
                    unidad VARCHAR(32) NOT NULL DEFAULT '',
                    minimo DECIMAL(30, 10) NOT NULL DEFAULT 0,
                    maximo DECIMAL(30, 10) NOT NULL DEFAULT 4294967295
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS envios_solicitudes (
                    clave CHAR(36) NOT NULL PRIMARY KEY,
                    envio_id BIGINT UNSIGNED NOT NULL,
                    creada_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_envios():
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                  """SELECT envios.id, instrumento_id, instrumento_nombre,
                         COALESCE(metadata.numero_serie, '') AS numero_serie,
                         COALESCE(metadata.tipo_instrumento, 'no especificado') AS tipo_instrumento,
                         COALESCE(medicion.perfil_id, 'personalizado') AS perfil_id,
                         CAST(medicion.valor_medicion AS CHAR) AS valor_medicion,
                         COALESCE(medicion.unidad, '') AS unidad,
                         CAST(medicion.minimo AS CHAR) AS minimo,
                         CAST(medicion.maximo AS CHAR) AS maximo,
                         valor, label_octal, sdi, dato_raw, ssm, arinc429_word,
                         arinc429_hex, arinc429_bin, arinc429_bytes_hex, salida_modo, creado_en
                     FROM envios
                     LEFT JOIN envios_metadata AS metadata ON metadata.envio_id = envios.id
                       LEFT JOIN envios_medicion AS medicion ON medicion.envio_id = envios.id
                     ORDER BY envios.id DESC"""
            )
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_envio(envio_id):
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                  """SELECT envios.id, instrumento_id, instrumento_nombre,
                         COALESCE(metadata.numero_serie, '') AS numero_serie,
                         COALESCE(metadata.tipo_instrumento, 'no especificado') AS tipo_instrumento,
                         COALESCE(medicion.perfil_id, 'personalizado') AS perfil_id,
                         CAST(medicion.valor_medicion AS CHAR) AS valor_medicion,
                         COALESCE(medicion.unidad, '') AS unidad,
                         CAST(medicion.minimo AS CHAR) AS minimo,
                         CAST(medicion.maximo AS CHAR) AS maximo,
                         valor, label_octal, sdi, dato_raw, ssm, arinc429_word,
                         arinc429_hex, arinc429_bin, arinc429_bytes_hex, salida_modo, creado_en
                     FROM envios
                     LEFT JOIN envios_metadata AS metadata ON metadata.envio_id = envios.id
                       LEFT JOIN envios_medicion AS medicion ON medicion.envio_id = envios.id
                     WHERE envios.id = %s""",
                (envio_id,),
            )
            return cursor.fetchone()
    finally:
        conexion.close()


def crear_envio(
    instrumento_id, instrumento_nombre, valor, dato_raw, numero_serie="",
    tipo_instrumento="no especificado", perfil_id="personalizado",
    valor_medicion=None, unidad="", minimo=0, maximo=4294967295,
    clave_solicitud=None,
):
    creado_en = datetime.now(timezone.utc).isoformat(timespec="seconds")
    palabra = decodificar_palabra(dato_raw)
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            if clave_solicitud:
                cursor.execute(
                    "SELECT envio_id FROM envios_solicitudes WHERE clave = %s",
                    (clave_solicitud,),
                )
                solicitud_existente = cursor.fetchone()
                if solicitud_existente:
                    conexion.rollback()
                    return obtener_envio(solicitud_existente["envio_id"])
            cursor.execute(
                """INSERT INTO envios
                         (instrumento_id, instrumento_nombre, valor, label_octal, sdi, dato_raw, ssm,
                          arinc429_word, arinc429_hex, arinc429_bin,
                          arinc429_bytes_hex, salida_modo, creado_en)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'simulacion', %s)""",
                     (
                          instrumento_id, instrumento_nombre, valor, palabra["label_octal"],
                          palabra["sdi"], palabra["dato_raw"], palabra["ssm"],
                          palabra["arinc429_word"], palabra["arinc429_hex"],
                          palabra["arinc429_bin"], palabra["arinc429_bytes_hex"], creado_en,
                     ),
            )
            envio_id = cursor.lastrowid
            cursor.execute(
                """INSERT INTO envios_metadata (envio_id, numero_serie, tipo_instrumento)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE numero_serie = VALUES(numero_serie),
                                           tipo_instrumento = VALUES(tipo_instrumento)""",
                (envio_id, numero_serie, tipo_instrumento),
            )
            cursor.execute(
                """INSERT INTO envios_medicion
                       (envio_id, perfil_id, valor_medicion, unidad, minimo, maximo)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (envio_id, perfil_id, valor_medicion, unidad, minimo, maximo),
            )
            if clave_solicitud:
                cursor.execute(
                    "INSERT INTO envios_solicitudes (clave, envio_id) VALUES (%s, %s)",
                    (clave_solicitud, envio_id),
                )
        conexion.commit()
        return obtener_envio(envio_id)
    except Exception as error:
        conexion.rollback()
        if clave_solicitud and getattr(error, "args", (None,))[0] == 1062:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT envio_id FROM envios_solicitudes WHERE clave = %s",
                    (clave_solicitud,),
                )
                solicitud_existente = cursor.fetchone()
            if solicitud_existente:
                return obtener_envio(solicitud_existente["envio_id"])
        raise
    finally:
        conexion.close()


def actualizar_envio(
    envio_id, instrumento_id, instrumento_nombre, valor, dato_raw, numero_serie="",
    tipo_instrumento="no especificado", perfil_id="personalizado",
    valor_medicion=None, unidad="", minimo=0, maximo=4294967295,
):
    palabra = decodificar_palabra(dato_raw)
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """UPDATE envios
                         SET instrumento_id = %s, instrumento_nombre = %s, valor = %s,
                       label_octal = %s, sdi = %s, dato_raw = %s, ssm = %s,
                       arinc429_word = %s, arinc429_hex = %s, arinc429_bin = %s,
                       arinc429_bytes_hex = %s, salida_modo = 'simulacion'
                   WHERE id = %s""",
                (
                    instrumento_id, instrumento_nombre, valor, palabra["label_octal"],
                    palabra["sdi"], palabra["dato_raw"], palabra["ssm"],
                    palabra["arinc429_word"], palabra["arinc429_hex"],
                    palabra["arinc429_bin"], palabra["arinc429_bytes_hex"], envio_id,
                ),
            )
            actualizado = cursor.rowcount > 0
            if not actualizado:
                cursor.execute("SELECT id FROM envios WHERE id = %s", (envio_id,))
                actualizado = cursor.fetchone() is not None
            if actualizado:
                cursor.execute(
                    """INSERT INTO envios_metadata (envio_id, numero_serie, tipo_instrumento)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE numero_serie = VALUES(numero_serie),
                                               tipo_instrumento = VALUES(tipo_instrumento)""",
                    (envio_id, numero_serie, tipo_instrumento),
                )
                cursor.execute(
                    """INSERT INTO envios_medicion
                           (envio_id, perfil_id, valor_medicion, unidad, minimo, maximo)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE perfil_id = VALUES(perfil_id),
                           valor_medicion = VALUES(valor_medicion), unidad = VALUES(unidad),
                           minimo = VALUES(minimo), maximo = VALUES(maximo)""",
                    (envio_id, perfil_id, valor_medicion, unidad, minimo, maximo),
                )
        conexion.commit()
        return obtener_envio(envio_id) if actualizado else None
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def eliminar_envio(envio_id):
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM envios_solicitudes WHERE envio_id = %s", (envio_id,))
            cursor.execute("DELETE FROM envios_medicion WHERE envio_id = %s", (envio_id,))
            cursor.execute("DELETE FROM envios_metadata WHERE envio_id = %s", (envio_id,))
            cursor.execute("DELETE FROM envios WHERE id = %s", (envio_id,))
            eliminado = cursor.rowcount > 0
        conexion.commit()
        return eliminado
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()