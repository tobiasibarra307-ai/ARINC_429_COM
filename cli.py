import argparse
import sys
import time

import database
from arinc429 import decodificar_palabra
from instrumentos import INSTRUMENTOS, INSTRUMENTOS_POR_ID


def mostrar_instrumentos():
    for instrumento in INSTRUMENTOS:
        print(f"{instrumento['id']:<6} {instrumento['nombre']}")


def mostrar_envios(envios):
    if not envios:
        print("No hay envíos registrados.")
        return

    columnas = [
        ("ID", lambda envio: str(envio["id"])),
        ("INSTRUMENTO", lambda envio: envio["instrumento_nombre"]),
        ("VALOR", lambda envio: envio["valor"]),
        ("ARINC429", lambda envio: envio["arinc429_hex"]),
        ("MODO", lambda envio: envio["salida_modo"]),
        ("FECHA UTC", lambda envio: envio["creado_en"]),
    ]
    anchos = [
        max(len(titulo), *(len(obtener(envio)) for envio in envios))
        for titulo, obtener in columnas
    ]
    formato = "  ".join(f"{{:<{ancho}}}" for ancho in anchos)
    print(formato.format(*(titulo for titulo, _ in columnas)))
    print(formato.format(*("-" * ancho for ancho in anchos)))
    for envio in envios:
        print(formato.format(*(obtener(envio) for _, obtener in columnas)))


def formatear_tabla_completa(envios):
    columnas = (
        ("ID", 4, lambda envio: envio["id"]),
        ("INSTRUMENTO", 32, lambda envio: envio["instrumento_nombre"]),
        ("SERIE", 16, lambda envio: envio.get("numero_serie") or "-"),
        ("TIPO", 14, lambda envio: envio.get("tipo_instrumento") or "-"),
        ("MEDICION", 18, lambda envio: _mostrar_numero(envio.get("valor_medicion"), envio.get("unidad"))),
        ("RANGO", 22, lambda envio: _mostrar_rango(envio)),
        ("ARINC HEX", 10, lambda envio: envio["arinc429_hex"]),
        ("BITS 32", 32, lambda envio: str(envio["arinc429_bin"]).zfill(32)),
    )
    anchos = [max(len(titulo), ancho) for titulo, ancho, _ in columnas]
    borde = "+" + "+".join("-" * (ancho + 2) for ancho in anchos) + "+"

    def fila(valores):
        celdas = []
        for valor, ancho in zip(valores, anchos):
            texto = str(valor).replace("\r", " ").replace("\n", " ")
            if len(texto) > ancho:
                texto = texto[:ancho - 1] + "~"
            celdas.append(f" {texto:<{ancho}} ")
        return "|" + "|".join(celdas) + "|"

    lineas = [borde, fila([titulo for titulo, _, _ in columnas]), borde]
    for envio in envios:
        lineas.append(fila([obtener(envio) for _, _, obtener in columnas]))
    lineas.append(borde)
    return "\n".join(lineas) if envios else "(0 filas)"


def _mostrar_numero(valor, unidad):
    if valor is None:
        return "-"
    numero = str(valor)
    if "." in numero:
        numero = numero.rstrip("0").rstrip(".")
    return f"{numero} {unidad or ''}".strip()


def _mostrar_rango(envio):
    minimo = envio.get("minimo")
    maximo = envio.get("maximo")
    if minimo is None or maximo is None:
        return "-"
    return f"{_mostrar_numero(minimo, '')}..{_mostrar_numero(maximo, envio.get('unidad'))}"


def vigilar_envios(intervalo=1.0, max_actualizaciones=None, sleeper=time.sleep):
    actualizaciones = 0
    try:
        while max_actualizaciones is None or actualizaciones < max_actualizaciones:
            envios = database.listar_envios()
            contenido = formatear_tabla_completa(envios)
            if sys.stdout.isatty():
                sys.stdout.write("\033[2J\033[H")
            print(f"ARINC-429 | Tabla MySQL | actualiza cada {intervalo:g} s | Ctrl+C para salir")
            print(contenido)
            sys.stdout.flush()
            actualizaciones += 1
            if max_actualizaciones is None or actualizaciones < max_actualizaciones:
                sleeper(intervalo)
    except KeyboardInterrupt:
        print("\nMonitoreo detenido.")


def validar_envio(instrumento_id, dato_raw):
    if not isinstance(instrumento_id, str) or not instrumento_id.strip():
        raise ValueError("El nombre del instrumento no puede estar vacío.")
    instrumento_id = instrumento_id.strip()
    if len(instrumento_id) > 120:
        raise ValueError("El nombre del instrumento no puede superar 120 caracteres.")
    instrumento = next(
        (
            item for item in INSTRUMENTOS
            if item["id"].casefold() == instrumento_id.casefold()
            or item["nombre"].casefold() == instrumento_id.casefold()
        ),
        {"id": "personalizado", "nombre": instrumento_id},
    )
    palabra = decodificar_palabra(dato_raw)
    return instrumento, str(dato_raw), palabra


def agregar_argumento_palabra(comando):
    comando.add_argument("--dato-raw", type=int, required=True, help="Palabra ARINC completa de 32 bits (0 a 4294967295)")
    comando.add_argument("--numero-serie", default="", help="Número de serie del instrumento")
    comando.add_argument(
        "--tipo-instrumento",
        choices=("analogico", "digital", "no especificado"),
        default="no especificado",
        help="Tipo de instrumento",
    )


def construir_parser():
    parser = argparse.ArgumentParser(
        prog="envios",
        description="Administrar envíos ARINC-429 en la base de datos MySQL local."
    )
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("listar", help="Mostrar todos los envíos")
    vigilar = comandos.add_parser("vigilar", help="Ver todos los campos y refrescar la tabla")
    vigilar.add_argument("--intervalo", type=float, default=1.0, help="Segundos entre actualizaciones (por defecto: 1)")
    comandos.add_parser("instrumentos", help="Mostrar los instrumentos disponibles")

    ver = comandos.add_parser("ver", help="Consultar un envío por ID")
    ver.add_argument("id", type=int)

    crear = comandos.add_parser("crear", help="Crear un envío")
    crear.add_argument("--instrumento", required=True, help="Nombre libre del instrumento")
    agregar_argumento_palabra(crear)

    actualizar = comandos.add_parser("actualizar", help="Editar un envío")
    actualizar.add_argument("id", type=int)
    actualizar.add_argument("--instrumento", required=True, help="Nombre libre del instrumento")
    agregar_argumento_palabra(actualizar)

    eliminar = comandos.add_parser("eliminar", help="Eliminar un envío")
    eliminar.add_argument("id", type=int)
    eliminar.add_argument("--confirmar", action="store_true", help="Eliminar sin pedir confirmación")
    return parser


def ejecutar(argumentos):
    if argumentos.comando == "instrumentos":
        mostrar_instrumentos()
        return
    if argumentos.comando == "listar":
        mostrar_envios(database.listar_envios())
        return
    if argumentos.comando == "vigilar":
        if argumentos.intervalo <= 0:
            raise ValueError("El intervalo debe ser mayor que cero.")
        vigilar_envios(argumentos.intervalo)
        return
    if hasattr(argumentos, "id") and argumentos.id < 1:
        raise ValueError("El ID debe ser un número positivo.")
    if argumentos.comando == "ver":
        envio = database.obtener_envio(argumentos.id)
        if envio is None:
            raise ValueError(f"No existe el envío con ID {argumentos.id}.")
        mostrar_envios([envio])
        return
    if argumentos.comando == "crear":
        instrumento, valor, palabra = validar_envio(
            argumentos.instrumento, argumentos.dato_raw,
        )
        envio = database.crear_envio(
            instrumento["id"], instrumento["nombre"], valor,
            palabra["dato_raw"], argumentos.numero_serie, argumentos.tipo_instrumento,
        )
        print(f"Envío simulado creado con ID {envio['id']}; ARINC-429 {envio['arinc429_hex']}.")
        mostrar_envios([envio])
        return
    if argumentos.comando == "actualizar":
        instrumento, valor, palabra = validar_envio(
            argumentos.instrumento, argumentos.dato_raw,
        )
        envio = database.actualizar_envio(
            argumentos.id, instrumento["id"], instrumento["nombre"], valor,
            palabra["dato_raw"], argumentos.numero_serie, argumentos.tipo_instrumento,
        )
        if envio is None:
            raise ValueError(f"No existe el envío con ID {argumentos.id}.")
        print("Envío actualizado.")
        mostrar_envios([envio])
        return
    if argumentos.comando == "eliminar":
        if not argumentos.confirmar:
            respuesta = input(f"¿Eliminar el envío {argumentos.id}? [s/N] ").strip().lower()
            if respuesta not in {"s", "si", "sí"}:
                print("Operación cancelada.")
                return
        if not database.eliminar_envio(argumentos.id):
            raise ValueError(f"No existe el envío con ID {argumentos.id}.")
        print(f"Envío {argumentos.id} eliminado.")


def main():
    parser = construir_parser()
    argumentos = parser.parse_args()
    try:
        database.inicializar_base_de_datos()
        ejecutar(argumentos)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Error MySQL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())