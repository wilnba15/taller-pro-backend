import hashlib
from datetime import date

DOCUMENT_TYPE_INVOICE = "01"
EMISSION_TYPE_NORMAL = "1"


def sri_environment_code(environment: str) -> str:
    normalized = (environment or "pruebas").strip().lower()
    if normalized in {"pruebas", "prueba", "test", "certificacion", "certificación", "1"}:
        return "1"
    if normalized in {"produccion", "producción", "production", "2"}:
        return "2"
    raise ValueError("Ambiente SRI no válido. Use 'pruebas' o 'produccion'.")


def modulo11_check_digit(value: str) -> str:
    if not value.isdigit():
        raise ValueError("La cadena para Módulo 11 debe contener solo números")

    factor = 2
    total = 0
    for char in reversed(value):
        total += int(char) * factor
        factor += 1
        if factor > 7:
            factor = 2

    result = 11 - (total % 11)
    if result == 11:
        return "0"
    if result == 10:
        return "1"
    return str(result)


def build_numeric_code(*, ruc: str, invoice_number: str, issue_date: date) -> str:
    seed = f"{ruc}|{invoice_number}|{issue_date.isoformat()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    number = int(digest[:16], 16) % 100_000_000
    return str(number).zfill(8)


def build_access_key(
    *,
    issue_date: date,
    ruc: str,
    environment: str,
    establishment_code: str,
    emission_point_code: str,
    sequential: int,
    numeric_code: str,
    document_type: str = DOCUMENT_TYPE_INVOICE,
    emission_type: str = EMISSION_TYPE_NORMAL,
) -> str:
    clean_ruc = "".join(char for char in str(ruc or "") if char.isdigit())
    if len(clean_ruc) != 13:
        raise ValueError("El RUC del emisor debe tener 13 dígitos")

    establishment = str(establishment_code).zfill(3)
    emission_point = str(emission_point_code).zfill(3)
    sequential_text = str(sequential).zfill(9)
    numeric_code_text = str(numeric_code).zfill(8)

    if len(establishment) != 3 or not establishment.isdigit():
        raise ValueError("El establecimiento debe tener 3 dígitos")
    if len(emission_point) != 3 or not emission_point.isdigit():
        raise ValueError("El punto de emisión debe tener 3 dígitos")
    if len(sequential_text) != 9 or not sequential_text.isdigit():
        raise ValueError("El secuencial debe tener 9 dígitos")
    if len(numeric_code_text) != 8 or not numeric_code_text.isdigit():
        raise ValueError("El código numérico debe tener 8 dígitos")

    base = (
        issue_date.strftime("%d%m%Y")
        + document_type
        + clean_ruc
        + sri_environment_code(environment)
        + establishment
        + emission_point
        + sequential_text
        + numeric_code_text
        + emission_type
    )

    if len(base) != 48:
        raise ValueError(f"La base de la clave de acceso debe tener 48 dígitos y tiene {len(base)}")

    return base + modulo11_check_digit(base)
