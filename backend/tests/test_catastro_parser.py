import pytest

from app.services.geocoding.catastro import Via, interpretar


def direccion(texto):
    via, p1, p2 = interpretar(texto)
    return via.codigos(), p1, p2


@pytest.mark.parametrize("texto,esperado", [
    ("Carrera 7 # 55-25", (["KR 7", "AK 7"], "55", "25")),
    ("Cra 7 55 25", (["KR 7", "AK 7"], "55", "25")),
    ("CL 80 No. 70-20, Bogotá", (["CL 80", "AC 80"], "70", "20")),
    ("Avenida Calle 26 # 69-76", (["AC 26"], "69", "76")),
    ("Calle 63 Sur # 80-15", (["CL 63 S", "AC 63 S"], "80", "15")),
    ("Carrera 14C # 12-30", (["KR 14C", "AK 14C"], "12", "30")),
    ("Carrera 90 bis # 130-44", (["KR 90BIS", "AK 90BIS"], "130", "44")),
    ("Diagonal 40A 12 5", (["DG 40A"], "12", "05")),   # el último número se completa a dos dígitos
])
def test_direcciones(texto, esperado):
    assert direccion(texto) == esperado


@pytest.mark.parametrize("texto,via_a,via_b", [
    ("Calle 72 con Carrera 10", "CL 72", "KR 10"),
    ("Av Boyacá con Calle 80", "AK 72", "CL 80"),
    ("Avenida Caracas y Calle 72", "AK 14", "CL 72"),
    ("Calle 26 con NQS", "CL 26", "AK 30"),
])
def test_esquinas(texto, via_a, via_b):
    a, b = interpretar(texto)
    assert isinstance(a, Via) and isinstance(b, Via)
    assert via_a in a.codigos() and via_b in b.codigos()


@pytest.mark.parametrize("texto", ["Portal 80", "Calle 80", "Unicentro", "Parque de la 93", "Galerías", ""])
def test_lo_que_no_es_direccion_se_deja_a_otro_proveedor(texto):
    assert interpretar(texto) is None


def test_la_placa_de_una_via_con_sentido_no_incluye_el_sufijo():
    assert Via(["KR"], "63 S").como_placa() == "63"
