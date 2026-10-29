import json
import os
import re
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import database
from arinc429 import decodificar_palabra
from instrumentos import (
    INSTRUMENTOS,
    INSTRUMENTOS_POR_ID,
    PERFILES_MEDICION,
    PERFILES_MEDICION_POR_ID,
)

BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))


class ManejadorEnvios(BaseHTTPRequestHandler):
    def responder_json(self, estado, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == "/api/instrumentos":
            try:
                self.responder_json(HTTPStatus.OK, database.listar_instrumentos())
            except Exception as error:
                self.error_base_de_datos(error)
            return

        if ruta == "/api/catalogo-instrumentos":
            catalogo = INSTRUMENTOS + PERFILES_MEDICION
            self.responder_json(HTTPStatus.OK, catalogo)
            return

        coincidencia = re.fullmatch(r"/api/instrumentos/(\d+)", ruta)
        if coincidencia:
            try:
                instrumento = database.obtener_instrumento(int(coincidencia.group(1)))
                if instrumento is None:
                    self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Instrumento no encontrado."})
                else:
                    self.responder_json(HTTPStatus.OK, instrumento)
            except Exception as error:
                self.error_base_de_datos(error)
            return

        if ruta == "/api/envios":
            try:
                self.responder_json(HTTPStatus.OK, database.listar_envios())
            except Exception as error:
                self.error_base_de_datos(error)
            return

        coincidencia = re.fullmatch(r"/api/envios/(\d+)", ruta)
        if coincidencia:
            try:
                envio = database.obtener_envio(int(coincidencia.group(1)))
                if envio is None:
                    self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Envío no encontrado."})
                else:
                    self.responder_json(HTTPStatus.OK, envio)
            except Exception as error:
                self.error_base_de_datos(error)
            return

        if ruta == "/":
            pagina = (BASE_DIR / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(pagina)))
            self.end_headers()
            self.wfile.write(pagina)
            return

        self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Recurso no encontrado."})

    def leer_envio(self):
        longitud = int(self.headers.get("Content-Length", "0"))
        if longitud < 1 or longitud > 16_384:
            raise ValueError
        datos = json.loads(self.rfile.read(longitud))
        if not isinstance(datos, dict):
            raise ValueError
        instrumento_nombre = datos.get("instrumento_nombre")
        instrumento_id = datos.get("instrumento_id")
        perfil_id = datos.get("perfil_id", "personalizado")
        numero_serie = datos.get("numero_serie", "")
        tipo_instrumento = datos.get("tipo_instrumento")
        dato_raw = datos.get("dato_raw")
        valor_medicion = datos.get("valor_medicion")
        minimo_enviado = datos.get("minimo")
        maximo_enviado = datos.get("maximo")
        unidad_enviada = datos.get("unidad", "")
        if not isinstance(perfil_id, str):
            raise ValueError("Selecciona un perfil de instrumento válido.")
        perfil = PERFILES_MEDICION_POR_ID.get(perfil_id)
        if perfil_id != "personalizado" and perfil is None:
            raise ValueError("Selecciona un perfil de instrumento válido.")
        instrumento_registrado = None
        if instrumento_id is not None:
            try:
                instrumento_registrado = database.obtener_instrumento(int(instrumento_id))
            except (TypeError, ValueError):
                instrumento_registrado = None
            if instrumento_registrado is None:
                raise ValueError("Selecciona un instrumento registrado válido.")
            if instrumento_registrado["estado"] != "activo":
                raise ValueError("Solo se pueden enviar instrumentos activos.")
            instrumento_nombre = instrumento_registrado["nombre"]
        else:
            if not isinstance(instrumento_nombre, str):
                raise ValueError("Selecciona un instrumento registrado.")
            instrumento_nombre = instrumento_nombre.strip()
            if perfil:
                instrumento_nombre = perfil["nombre"]
            elif not instrumento_nombre or len(instrumento_nombre) > 120:
                raise ValueError("El nombre del instrumento debe tener entre 1 y 120 caracteres.")
        if not isinstance(numero_serie, str) or len(numero_serie.strip()) > 120:
            raise ValueError("El número de serie no puede superar 120 caracteres.")
        numero_serie = numero_serie.strip()
        if not isinstance(tipo_instrumento, str) or tipo_instrumento not in {"analogico", "digital"}:
            raise ValueError("Selecciona si el instrumento es analógico o digital.")
        if perfil:
            minimo = Decimal(str(perfil["minimo"]))
            maximo = Decimal(str(perfil["maximo"]))
            unidad = perfil["unidad"]
        else:
            try:
                minimo = Decimal(str(minimo_enviado))
                maximo = Decimal(str(maximo_enviado))
            except (InvalidOperation, TypeError):
                raise ValueError("Indica un mínimo y máximo numéricos para el perfil personalizado.")
            if not minimo.is_finite() or not maximo.is_finite() or minimo >= maximo:
                raise ValueError("El máximo personalizado debe ser mayor que el mínimo.")
            unidad = unidad_enviada.strip() if isinstance(unidad_enviada, str) else ""
            if len(unidad) > 32:
                raise ValueError("La unidad no puede superar 32 caracteres.")
        try:
            medicion = Decimal(str(valor_medicion))
        except (InvalidOperation, TypeError):
            raise ValueError("Ingresa un valor medido numérico.")
        if not medicion.is_finite() or not minimo <= medicion <= maximo:
            raise ValueError(f"El valor debe estar entre {minimo} y {maximo} {unidad}.")
        if instrumento_registrado:
            instrumento = {"id": str(instrumento_registrado["id"]), "nombre": instrumento_nombre}
        else:
            instrumento = (
                {"id": perfil_id, "nombre": instrumento_nombre}
                if perfil
                else next(
                    (
                        item for item in INSTRUMENTOS
                        if item["id"].casefold() == instrumento_nombre.casefold()
                        or item["nombre"].casefold() == instrumento_nombre.casefold()
                    ),
                    {"id": "personalizado", "nombre": instrumento_nombre},
                )
            )
        palabra = decodificar_palabra(dato_raw)
        return (
            instrumento, str(dato_raw), palabra, numero_serie, tipo_instrumento,
            perfil_id, str(medicion), unidad, str(minimo), str(maximo),
        )

    def error_datos(self, error):
        detalle = str(error) or "Envía un instrumento y un valor de hasta 500 caracteres."
        self.responder_json(HTTPStatus.BAD_REQUEST, {"error": detalle})

    def error_base_de_datos(self, error):
        print(f"Error MySQL: {error}")
        self.responder_json(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"error": "No se pudo conectar con la base de datos MySQL."},
        )

    def leer_instrumento(self):
        longitud = int(self.headers.get("Content-Length", "0"))
        if longitud < 1 or longitud > 16_384:
            raise ValueError("El formulario del instrumento no es válido.")
        datos = json.loads(self.rfile.read(longitud))
        if not isinstance(datos, dict):
            raise ValueError("El cuerpo debe ser un objeto JSON.")
        nombre = datos.get("nombre")
        nombres_permitidos = {item["nombre"] for item in INSTRUMENTOS + PERFILES_MEDICION}
        if nombre not in nombres_permitidos:
            raise ValueError("Selecciona un instrumento del catálogo aeronáutico.")
        estado = datos.get("estado", "activo")
        if estado not in {"activo", "mantenimiento", "inactivo"}:
            raise ValueError("Selecciona un estado válido.")
        resultado = {"nombre": nombre, "estado": estado}
        limites = {"modelo": 100, "fabricante": 150, "tipo": 100}
        for campo, limite in limites.items():
            valor = datos.get(campo, "")
            if not isinstance(valor, str) or len(valor.strip()) > limite:
                raise ValueError(f"El campo {campo} no puede superar {limite} caracteres.")
            resultado[campo] = valor.strip() or None
        descripcion = datos.get("descripcion", "")
        if not isinstance(descripcion, str):
            raise ValueError("La descripción debe ser texto.")
        resultado["descripcion"] = descripcion.strip() or None
        return resultado

    def responder_error_validacion(self, error):
        self.responder_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_POST(self):
        ruta = urlparse(self.path).path
        if ruta == "/api/instrumentos":
            try:
                instrumento = database.crear_instrumento(self.leer_instrumento())
                self.responder_json(HTTPStatus.CREATED, instrumento)
            except (ValueError, json.JSONDecodeError) as error:
                self.responder_error_validacion(error)
            except Exception as error:
                self.error_base_de_datos(error)
            return

        if ruta != "/api/envios":
            self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Recurso no encontrado."})
            return

        clave_solicitud = self.headers.get("Idempotency-Key", "")
        try:
            clave_solicitud = str(UUID(clave_solicitud))
        except (ValueError, AttributeError):
            self.responder_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Falta una clave válida para evitar envíos duplicados."},
            )
            return

        try:
            (
                instrumento, valor, palabra, numero_serie, tipo_instrumento,
                perfil_id, valor_medicion, unidad, minimo, maximo,
            ) = self.leer_envio()
        except (ValueError, json.JSONDecodeError) as error:
            self.error_datos(error)
            return

        try:
            envio = database.crear_envio(
                instrumento["id"], instrumento["nombre"], valor,
                palabra["dato_raw"], numero_serie, tipo_instrumento,
                perfil_id, valor_medicion, unidad, minimo, maximo,
                clave_solicitud,
            )
            self.responder_json(HTTPStatus.CREATED, envio)
        except Exception as error:
            self.error_base_de_datos(error)

    def do_PUT(self):
        ruta = urlparse(self.path).path
        coincidencia = re.fullmatch(r"/api/instrumentos/(\d+)", ruta)
        if coincidencia:
            try:
                instrumento = database.actualizar_instrumento(
                    int(coincidencia.group(1)), self.leer_instrumento()
                )
                if instrumento is None:
                    self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Instrumento no encontrado."})
                else:
                    self.responder_json(HTTPStatus.OK, instrumento)
            except (ValueError, json.JSONDecodeError) as error:
                self.responder_error_validacion(error)
            except Exception as error:
                self.error_base_de_datos(error)
            return

        coincidencia = re.fullmatch(r"/api/envios/(\d+)", ruta)
        if not coincidencia:
            self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Recurso no encontrado."})
            return
        try:
            (
                instrumento, valor, palabra, numero_serie, tipo_instrumento,
                perfil_id, valor_medicion, unidad, minimo, maximo,
            ) = self.leer_envio()
        except (ValueError, json.JSONDecodeError) as error:
            self.error_datos(error)
            return
        try:
            envio = database.actualizar_envio(
                int(coincidencia.group(1)), instrumento["id"], instrumento["nombre"], valor,
                palabra["dato_raw"], numero_serie, tipo_instrumento,
                perfil_id, valor_medicion, unidad, minimo, maximo,
            )
            if envio is None:
                self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Envío no encontrado."})
            else:
                self.responder_json(HTTPStatus.OK, envio)
        except Exception as error:
            self.error_base_de_datos(error)

    def do_DELETE(self):
        ruta = urlparse(self.path).path
        coincidencia = re.fullmatch(r"/api/instrumentos/(\d+)", ruta)
        if coincidencia:
            try:
                if database.eliminar_instrumento(int(coincidencia.group(1))):
                    self.responder_json(HTTPStatus.OK, {"eliminado": True})
                else:
                    self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Instrumento no encontrado."})
            except Exception as error:
                self.error_base_de_datos(error)
            return

        coincidencia = re.fullmatch(r"/api/envios/(\d+)", ruta)
        if not coincidencia:
            self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Recurso no encontrado."})
            return
        try:
            eliminado = database.eliminar_envio(int(coincidencia.group(1)))
            if eliminado:
                self.responder_json(HTTPStatus.OK, {"eliminado": True})
            else:
                self.responder_json(HTTPStatus.NOT_FOUND, {"error": "Envío no encontrado."})
        except Exception as error:
            self.error_base_de_datos(error)

    def log_message(self, formato, *argumentos):
        print(f"[{self.log_date_time_string()}] {formato % argumentos}")


if __name__ == "__main__":
    try:
        database.inicializar_base_de_datos()
    except Exception as error:
        raise SystemExit(f"No se pudo inicializar MySQL: {error}") from error
    servidor = ThreadingHTTPServer((HOST, PORT), ManejadorEnvios)
    print(f"Servidor disponible en http://{HOST}:{PORT}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        servidor.server_close()