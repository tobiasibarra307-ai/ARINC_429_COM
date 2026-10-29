"""Forward 32-bit words from an Arduino serial port to the ARINC-429 web app."""

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import serial


MAX_WORD = (1 << 32) - 1


def parse_word(line):
    value = line.strip()
    if not value:
        raise ValueError("línea vacía")
    if value.startswith(("0x", "0X")):
        word = int(value[2:], 16)
    elif value.startswith(("0b", "0B")):
        word = int(value[2:], 2)
    elif len(value) == 32 and set(value) <= {"0", "1"}:
        word = int(value, 2)
    else:
        word = int(value, 10)
    if not 0 <= word <= MAX_WORD:
        raise ValueError("la palabra debe estar entre 0 y 4294967295")
    return word


def send_word(url, word, serial_number="", idempotency_key=None):
    payload = {
        "instrumento_nombre": "Entrada Arduino",
        "numero_serie": serial_number,
        "tipo_instrumento": "digital",
        "perfil_id": "personalizado",
        "valor_medicion": str(word),
        "unidad": "raw",
        "minimo": "0",
        "maximo": str(MAX_WORD),
        "dato_raw": word,
    }
    request = Request(
        url.rstrip("/") + "/api/envios",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key or str(uuid4()),
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main():
    parser = argparse.ArgumentParser(
        description="Lee palabras ARINC de 32 bits por serial y las guarda en Yegro."
    )
    parser.add_argument("--port", required=True, help="Puerto serial, por ejemplo /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200, help="Velocidad serial (predeterminado: 115200)")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="URL base de Yegro ARINC-429")
    parser.add_argument("--serial-number", default="", help="Número de serie del Arduino o dispositivo")
    args = parser.parse_args()

    print(f"Leyendo {args.port} a {args.baud} baudios; destino: {args.url}")
    try:
        with serial.Serial(args.port, args.baud, timeout=1) as device:
            while True:
                line = device.readline().decode("ascii", errors="replace").strip()
                if not line:
                    continue
                try:
                    word = parse_word(line)
                except ValueError as error:
                    print(f"Línea ignorada {line!r}: {error}")
                    continue

                idempotency_key = str(uuid4())
                while True:
                    try:
                        envio = send_word(
                            args.url, word, args.serial_number, idempotency_key
                        )
                        print(f"Guardado envío {envio['id']}: {word} ({word:#010x})")
                        break
                    except HTTPError as error:
                        detalle = error.read().decode("utf-8", errors="replace")
                        if error.code < 500:
                            print(f"El servidor rechazó {word}: HTTP {error.code} {detalle}")
                            break
                        print(f"Servidor no disponible (HTTP {error.code}); reintento en 2 s")
                        time.sleep(2)
                    except (URLError, TimeoutError, OSError) as error:
                        print(f"No se pudo enviar {word}: {error}; reintento en 2 s")
                        time.sleep(2)
    except serial.SerialException as error:
        raise SystemExit(f"No se pudo abrir el puerto serial: {error}") from error
    except KeyboardInterrupt:
        print("\nPuente serial detenido.")


if __name__ == "__main__":
    main()