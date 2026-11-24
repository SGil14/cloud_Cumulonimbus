# Despliega Cumulonimbus completo en el clúster de Kubernetes local (Docker Desktop):
# app + PostgreSQL + Prometheus + Grafana. Se puede correr varias veces sin problema.
#
# Uso (desde la raíz del repositorio, con Kubernetes de Docker Desktop encendido):
#   powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1
#
# La primera vez crea los Secrets con contraseñas aleatorias (no se escriben en ningún archivo).

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz
$IMAGEN = "cumulonimbus:latest"

function Clave { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ }) }

Write-Host "`n1. Construyendo la imagen $IMAGEN ..." -ForegroundColor Cyan
docker build -t $IMAGEN .
if ($LASTEXITCODE) { throw "Falló docker build" }

Write-Host "`n2. Namespaces y configuración ..." -ForegroundColor Cyan
kubectl apply -f k8s/00-namespace.yaml -f k8s/monitoreo/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml

Write-Host "`n3. Secrets (solo si no existen) ..." -ForegroundColor Cyan
kubectl get secret cumulonimbus-secretos -n cumulonimbus *> $null
if ($LASTEXITCODE) {
  $pg = Clave
  kubectl create secret generic cumulonimbus-secretos -n cumulonimbus `
    --from-literal=POSTGRES_PASSWORD=$pg `
    --from-literal=DATABASE_URL="postgresql+psycopg://lluvia_app:$pg@postgres:5432/lluvia_bogota"
} else { Write-Host "   cumulonimbus-secretos ya existe" }
kubectl get secret grafana-admin -n monitoreo *> $null
if ($LASTEXITCODE) {
  $gf = Clave
  kubectl create secret generic grafana-admin -n monitoreo --from-literal=admin-user=admin --from-literal=admin-password=$gf
  Write-Host "   Grafana: usuario admin / contraseña $gf  (guárdala; también: kubectl get secret grafana-admin -n monitoreo -o jsonpath='{.data.admin-password}')" -ForegroundColor Yellow
} else { Write-Host "   grafana-admin ya existe" }

Write-Host "`n4. PostgreSQL ..." -ForegroundColor Cyan
kubectl apply -f k8s/10-postgres.yaml
kubectl rollout status statefulset/postgres -n cumulonimbus --timeout=180s

Write-Host "`n5. Migraciones (Job) ..." -ForegroundColor Cyan
kubectl delete job migraciones -n cumulonimbus --ignore-not-found
kubectl apply -f k8s/20-migraciones-job.yaml
kubectl wait --for=condition=complete job/migraciones -n cumulonimbus --timeout=180s

Write-Host "`n6. API (2 réplicas), recolector y autoescalado ..." -ForegroundColor Cyan
kubectl apply -f k8s/30-api.yaml -f k8s/31-recolector.yaml -f k8s/40-hpa.yaml
# Si la imagen cambió, que las réplicas la tomen (el tag :latest no cambia de nombre).
kubectl rollout restart deployment/api deployment/recolector -n cumulonimbus
kubectl rollout status deployment/api -n cumulonimbus --timeout=180s

Write-Host "`n7. Prometheus y Grafana ..." -ForegroundColor Cyan
kubectl apply -f k8s/monitoreo/10-prometheus.yaml -f k8s/monitoreo/20-grafana.yaml
kubectl rollout restart deployment/prometheus deployment/grafana -n monitoreo
kubectl rollout status deployment/grafana -n monitoreo --timeout=180s

Write-Host "`nListo:" -ForegroundColor Green
kubectl get pods,svc -n cumulonimbus
kubectl get pods,svc -n monitoreo
Write-Host "`n  App:        http://localhost"
Write-Host "  Métricas:   http://localhost/metrics"
Write-Host "  Prometheus: http://localhost:9090"
Write-Host "  Grafana:    http://localhost:3000"
Write-Host "  Tráfico:    python scripts/trafico.py --segundos 120 --usuarios 20"
