# app/accounts/validators.py
import re
from django.core.exceptions import ValidationError

RUT_RE = re.compile(r"^\d{7,8}-[\dkK]$")

def rut_is_valid(rut: str) -> bool:
    # Valida formato y dígito verificador (MVP: formato + DV básico)
    rut = rut.strip()
    if not RUT_RE.match(rut):
        return False
    cuerpo, dv = rut.split("-")
    dv = dv.lower()
    suma = 0
    factor = 2
    for c in reversed(cuerpo):
        suma += int(c) * factor
        factor = 2 if factor == 7 else factor + 1
    res = 11 - (suma % 11)
    dv_calc = "0" if res == 11 else "k" if res == 10 else str(res)
    return dv == dv_calc

def validate_rut(value: str):
    if not rut_is_valid(value):
        raise ValidationError("RUT inválido. Use formato 12345678-9")
