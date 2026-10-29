"""Codificación de palabras ARINC 429 para simulación y validación."""


MAX_DATO = (1 << 19) - 1
MAX_PALABRA = (1 << 32) - 1


def decodificar_palabra(palabra_raw):
    if (
        not isinstance(palabra_raw, int)
        or isinstance(palabra_raw, bool)
        or not 0 <= palabra_raw <= MAX_PALABRA
    ):
        raise ValueError("La palabra ARINC debe ser un entero entre 0 y 4294967295.")

    label_invertido = palabra_raw & 0xFF
    label = int(f"{label_invertido:08b}"[::-1], 2)
    return {
        "label_octal": f"{label:03o}",
        "sdi": (palabra_raw >> 8) & 0b11,
        "dato_raw": palabra_raw,
        "ssm": (palabra_raw >> 29) & 0b11,
        "arinc429_word": palabra_raw,
        "arinc429_hex": f"0x{palabra_raw:08X}",
        "arinc429_bin": f"{palabra_raw:032b}",
        "arinc429_bytes_hex": palabra_raw.to_bytes(4, byteorder="big").hex(" ").upper(),
    }


def codificar_palabra(label_octal, sdi, dato, ssm):
    if not isinstance(label_octal, str) or not label_octal or any(
        digito not in "01234567" for digito in label_octal
    ):
        raise ValueError("El label debe escribirse en octal, por ejemplo 203.")
    label = int(label_octal, 8)
    if label > 0xFF:
        raise ValueError("El label octal debe estar entre 000 y 377.")
    if not isinstance(sdi, int) or isinstance(sdi, bool) or not 0 <= sdi <= 3:
        raise ValueError("SDI debe ser un entero entre 0 y 3.")
    if not isinstance(dato, int) or isinstance(dato, bool) or not 0 <= dato <= MAX_DATO:
        raise ValueError("El dato bruto debe ser un entero entre 0 y 524287.")
    if not isinstance(ssm, int) or isinstance(ssm, bool) or not 0 <= ssm <= 3:
        raise ValueError("SSM debe ser un entero entre 0 y 3.")

    label_invertido = int(f"{label:08b}"[::-1], 2)
    palabra = label_invertido | (sdi << 8) | (dato << 10) | (ssm << 29)
    if palabra.bit_count() % 2 == 0:
        palabra |= 1 << 31

    return {
        "label_octal": f"{label:03o}",
        "sdi": sdi,
        "dato_raw": dato,
        "ssm": ssm,
        "arinc429_word": palabra,
        "arinc429_hex": f"0x{palabra:08X}",
        "arinc429_bin": f"{palabra:032b}",
        "arinc429_bytes_hex": palabra.to_bytes(4, byteorder="big").hex(" ").upper(),
    }