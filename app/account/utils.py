# app/accounts/utils.py
import re

RUT_RE = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d{1,8})-([\dkK])$")

def rut_is_valid(rut_str: str) -> bool:
    """
    Valida RUT Chileno. Acepta '12.345.678-5' o '12345678-5'.
    """
    if not rut_str:
        return False
    m = RUT_RE.match(rut_str)
    if not m:
        return False
    number = m.group(1).replace(".", "")
    dv = m.group(2).upper()

    s = 0
    multiplier = 2
    for digit in map(int, reversed(number)):
        s += digit * multiplier
        multiplier = 2 if multiplier == 7 else multiplier + 1
    res = 11 - (s % 11)
    dv_calc = "0" if res == 11 else "K" if res == 10 else str(res)
    return dv == dv_calc
