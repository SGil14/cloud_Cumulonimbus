"""El dashboard de Grafana, el de Kubernetes y las métricas de la API deben contar la misma historia."""

import json
import re
from pathlib import Path

import yaml
from prometheus_client import REGISTRY

from app.core import metricas  # noqa: F401  (registra las métricas)

RAIZ = Path(__file__).resolve().parents[2]
DASHBOARD = RAIZ / "monitoreo" / "grafana" / "dashboards" / "cumulonimbus.json"
CONFIGMAP = RAIZ / "k8s" / "monitoreo" / "20-grafana.yaml"
SUFIJOS = ("", "_total", "_bucket", "_sum", "_count", "_created")


def dashboard_de_archivo() -> dict:
    return json.loads(DASHBOARD.read_text(encoding="utf-8"))


def dashboard_de_kubernetes() -> dict:
    for doc in yaml.safe_load_all(CONFIGMAP.read_text(encoding="utf-8")):
        if doc and doc.get("metadata", {}).get("name") == "grafana-dashboard-cumulonimbus":
            return json.loads(doc["data"]["cumulonimbus.json"])
    raise AssertionError("No está el ConfigMap del dashboard")


def test_el_dashboard_de_compose_y_el_de_kubernetes_son_el_mismo():
    assert dashboard_de_archivo() == dashboard_de_kubernetes()


def test_el_dashboard_tiene_al_menos_tres_paneles_y_los_de_ia():
    paneles = dashboard_de_archivo()["panels"]
    assert len(paneles) >= 3
    assert len({p["id"] for p in paneles}) == len(paneles)  # ids únicos
    assert sum("IA ·" in p["title"] for p in paneles) >= 3


def test_cada_consulta_del_dashboard_usa_metricas_que_existen():
    existentes = {
        familia.name + sufijo for familia in REGISTRY.collect() for sufijo in SUFIJOS
    }
    for panel in dashboard_de_archivo()["panels"]:
        for objetivo in panel["targets"]:
            usadas = set(re.findall(r"\b(cumulonimbus_[a-z0-9_]+)", objetivo["expr"]))
            if re.match(r"sum\(up\{", objetivo["expr"]):  # `up` es una métrica de Prometheus, no de la API
                continue
            assert usadas, f"El panel «{panel['title']}» no usa ninguna métrica de la API"
            assert usadas <= existentes, f"«{panel['title']}» usa métricas inexistentes: {usadas - existentes}"


def test_las_etiquetas_del_dashboard_existen_en_la_configuracion_de_compose():
    prometheus = yaml.safe_load((RAIZ / "monitoreo" / "prometheus.yml").read_text(encoding="utf-8"))
    etiquetas = prometheus["scrape_configs"][0]["static_configs"][0]["labels"]
    texto = DASHBOARD.read_text(encoding="utf-8")
    assert 'componente=\\"cumulonimbus-api\\"' in texto and etiquetas["componente"] == "cumulonimbus-api"
    assert "{{pod}}" in texto and "pod" in etiquetas


def test_compose_levanta_la_api_prometheus_y_grafana():
    compose = yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
    assert {"app", "db", "prometheus", "grafana"} <= set(compose["services"])
    assert "app:8000" in (RAIZ / "monitoreo" / "prometheus.yml").read_text(encoding="utf-8")
