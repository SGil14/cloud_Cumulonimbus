# Guion de la demo: Kubernetes y monitoreo

Parte de la sustentación del Proyecto 3 (unos 4 de los 8 minutos de demostración). Sirve igual en el clúster
local (Docker Desktop) y en AKS: en AKS cambia `localhost` por la `EXTERNAL-IP` de cada Service.

## Antes de entrar (10 minutos antes)

- [ ] Docker Desktop abierto y Kubernetes en verde (o el AKS encendido: `az aks start -g rg-cumulonimbus-k8s -n aks-cumulonimbus`).
- [ ] `kubectl get pods -A` sin pods en error.
- [ ] Pestañas abiertas: la app, Grafana (sesión iniciada en el dashboard «Cumulonimbus · API en Kubernetes») y Prometheus → *Status → Targets*.
- [ ] Una terminal en la raíz del repositorio, con letra grande.

## 1. Lo que corre en el clúster (1 min)

```powershell
kubectl get pods,svc -n cumulonimbus
```

Qué decir:
- «La API tiene **2 réplicas** detrás de un **Service** que reparte el tráfico.»
- «El **recolector** va aparte, con 1 réplica, para no consultar el SAB dos veces cada 5 minutos.»
- «**PostgreSQL** es un **StatefulSet** con volumen persistente; las migraciones corrieron en un **Job** (`Completed`).»

```powershell
kubectl get pods,svc -n monitoreo
```

- «Prometheus y Grafana corren **dentro del clúster**, en su propio namespace.»

## 2. Configuración y secretos (30 s)

```powershell
kubectl get configmap cumulonimbus-config -n cumulonimbus -o yaml
kubectl get secret cumulonimbus-secretos -n cumulonimbus
```

- «La configuración no sensible está en un **ConfigMap**. La contraseña de la base y la llave de los tokens están en un **Secret**, que nunca se sube al repositorio: en el repo solo está `k8s/secret.example.yaml`.»

## 3. Salud y recursos (30 s)

```powershell
kubectl describe deployment api -n cumulonimbus | Select-String -Pattern "Liveness|Readiness|Limits|Requests" -Context 0,2
```

- «**Readiness** revisa la base de datos: si una réplica no llega a PostgreSQL, deja de recibir tráfico. **Liveness** solo revisa que el proceso responda, para no reiniciar todo por una caída de la base.»
- «Cada contenedor tiene **requests y limits** de CPU y memoria.»

## 4. Tráfico, Grafana y autoescalado (2 min)

En una terminal:

```powershell
kubectl get hpa -n cumulonimbus -w
```

En otra:

```powershell
python scripts/trafico.py --segundos 150 --usuarios 60
```

Mientras corre, mostrar Grafana:
- **Throughput**: sube a unas 15–20 peticiones por segundo.
- **Latencia p50 y p95**.
- **Peticiones en curso por réplica**: la carga se reparte entre los pods.
- **Estaciones con lluvia**: el gauge propio de la app.

Volver a la terminal del HPA:
- «Cuando la CPU pasa del 50 %, el **HorizontalPodAutoscaler** crea otra réplica.» Se ve `REPLICAS` pasar de 2 a 3.

```powershell
kubectl get pods -n cumulonimbus -l app=cumulonimbus-api
```

## 5. Si preguntan

| Pregunta | Respuesta corta |
|---|---|
| ¿Cómo llega la imagen al clúster? | El pipeline de GitHub Actions corre las pruebas, construye la imagen y la publica con etiqueta de versión (`sha-xxxxxxx`) en el registro. En AKS, el ACR está conectado al clúster con identidad administrada, sin contraseñas. |
| ¿Qué pasa si se cae un pod? | El Deployment crea otro para mantener 2 réplicas. Se puede mostrar con `kubectl delete pod <uno-de-la-api> -n cumulonimbus`. |
| ¿Cómo descubre Prometheus los pods? | Por las anotaciones `prometheus.io/scrape: "true"` en los pods; tiene permisos (RBAC) para listar pods. |
| ¿Por qué el recolector va aparte? | Si cada réplica recolectara, el SAB recibiría una consulta por réplica cada 5 minutos. |
| ¿Cómo se actualiza sin cortar el servicio? | `RollingUpdate` con `maxUnavailable: 0`: primero arranca la réplica nueva y luego se apaga la vieja. |
