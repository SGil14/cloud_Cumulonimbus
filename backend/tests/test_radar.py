import io
import zipfile
from datetime import timedelta

import pytest

from app.services import radar

KML = """<kml xmlns="http://earth.google.com/kml/2.2"><Folder>
<name>1399BOG-Intensity (Horizontal)-Wed Oct 14 16:17:48 2026 GMT</name>
<GroundOverlay><Icon><href>capa.png</href></Icon>
<LatLonBox><north>5.2</north><south>4.1</south><east>-73.5</east><west>-74.6</west></LatLonBox>
</GroundOverlay></Folder></kml>"""


def kmz(kml=KML, png=b"\x89PNG-falso"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", kml)
        z.writestr("capa.png", png)
    return buf.getvalue()


def test_interpreta_limites_imagen_y_hora_de_bogota():
    d = radar.interpretar_kmz(kmz())
    assert (d["norte"], d["sur"], d["este"], d["oeste"]) == (5.2, 4.1, -73.5, -74.6)
    assert d["imagen"].startswith("data:image/png;base64,")
    assert d["capturado_en"].utcoffset() == timedelta(hours=-5)
    assert d["capturado_en"].strftime("%H:%M") == "11:17"  # 16:17 GMT


def test_kmz_invalido_lanza_radar_error():
    with pytest.raises(radar.RadarError):
        radar.interpretar_kmz(b"no es un zip")


def test_kml_sin_imagen_lanza_radar_error():
    with pytest.raises(radar.RadarError):
        radar.interpretar_kmz(kmz(kml="<kml><Folder><name>x</name></Folder></kml>"))
