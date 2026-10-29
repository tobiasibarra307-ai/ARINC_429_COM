INSTRUMENTOS = [
    {"id": "adc", "nombre": "ADC - Computador de datos de aire"},
    {"id": "ahrs", "nombre": "AHRS - Referencia de actitud y rumbo"},
    {"id": "fms", "nombre": "FMS - Sistema de gestión de vuelo"},
    {"id": "gps", "nombre": "GPS - Sistema de posicionamiento"},
]
INSTRUMENTOS_POR_ID = {instrumento["id"]: instrumento for instrumento in INSTRUMENTOS}

PERFILES_MEDICION = [
    {
        "id": "velocidad",
        "nombre": "Velocímetro (velocidad indicada)",
        "minimo": 0,
        "maximo": 600,
        "unidad": "kt",
        "nota": "Rango nominal de referencia; depende del modelo de aeronave.",
    },
    {
        "id": "altitud",
        "nombre": "Altímetro",
        "minimo": -1000,
        "maximo": 60000,
        "unidad": "ft",
        "nota": "Rango nominal de referencia; confirma el límite del altímetro instalado.",
    },
    {
        "id": "rumbo",
        "nombre": "Brújula magnética (rumbo)",
        "minimo": 0,
        "maximo": 360,
        "unidad": "°",
        "nota": "Ciclo de rumbo nominal; la indicación 360° equivale a 0°.",
    },
    {
        "id": "velocidad_vertical",
        "nombre": "Indicador de velocidad vertical",
        "minimo": -6000,
        "maximo": 6000,
        "unidad": "ft/min",
        "nota": "Rango nominal de referencia; depende de la escala del instrumento.",
    },
    {
        "id": "actitud",
        "nombre": "Indicador de actitud (eje angular)",
        "minimo": -90,
        "maximo": 90,
        "unidad": "°",
        "nota": "Rango angular nominal por eje; confirma la escala del equipo.",
    },
    {
        "id": "temperatura_exterior",
        "nombre": "Temperatura exterior",
        "minimo": -80,
        "maximo": 60,
        "unidad": "°C",
        "nota": "Rango nominal amplio de referencia, no límite de certificación.",
    },
]
PERFILES_MEDICION_POR_ID = {
    perfil["id"]: perfil for perfil in PERFILES_MEDICION
}