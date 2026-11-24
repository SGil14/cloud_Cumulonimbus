# Despliega Cumulonimbus completo en Kubernetes: app + PostgreSQL + Prometheus + Grafana.
# Sirve para el clúster local (Docker Desktop) y para AKS. Se puede correr varias veces sin problema.
#
# Uso (desde la raíz del repositorio, con kubectl apuntando al clúster):
#   Local (Docker Desktop):
#     powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1
#   AKS (construye la imagen y la sube al ACR conectado al clúster; AKS ya trae metrics-server):
#     powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1 -Acr acrcumulonimbusk8s1234 -SinMetricsServer
#   Con una imagen ya publicada (por ejemplo la del pipeline):
#     ... -Imagen ghcr.io/sgil14/cloud_cumulonimbus:sha-abc1234
#
# Cada despliegue usa una etiqueta de versión (sha-<commit>), nunca solo "latest".
# La primera vez crea los Secrets con contraseñas aleatorias (no se escriben en ningún archivo).

param(
  [string]$Imagen = "",          # imagen ya construida; si se omite, se construye aquí
  [string]$Acr = "",             # nombre del Azure Container Registry al que subir la imagen (AKS)
  [switch]$SinMetricsServer      # AKS y otros clústeres administrados ya lo traen
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz

function Clave { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ }) }

# Aplica un manifiesto cambiando la imagen de ejemplo (cumulonimbus:latest) por la versión que se despliega.
function AplicarConImagen($archivo) {
  (Get-Content $archivo -Raw) -replace 'image: cumulonimbus:latest', "image: $Imagen" | kubectl apply -f -
  if ($LASTEXITCODE) { throw "Falló kubectl apply de $archivo" }
}

if (-not $Imagen) {
  $version = "sha-" + (git rev-parse --short=7 HEAD)
  $Imagen = if ($Acr) { "$Acr.azurecr.io/cumulonimbus:$version" } else { "cumulonimbus:$version" }
  Write-Host "`n1. Construyendo la imagen $Imagen ..." -ForegroundColor Cyan
  docker build -t $Imagen .
  if ($LASTEXITCODE) { throw "Falló docker build" }
  if ($Acr) {
    az acr login --name $Acr
    docker push $Imagen
    if ($LASTEXITCODE) { throw "Falló docker push al ACR" }
  }
} else {
  Write-Host "`n1. Usando la imagen ya publicada $Imagen" -ForegroundColor Cyan
}

Write-Host "`n2. Namespaces y configuración ..." -ForegroundColor Cyan
kubectl apply -f k8s/00-namespace.yaml -f k8s/monitoreo/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml

Write-Host "`n3. Secrets (solo si no existen) ..." -ForegroundColor Cyan
if (-not (kubectl get secret cumulonimbus-secretos -n cumulonimbus --ignore-not-found -o name)) {
  $pg = Clave
  kubectl create secret generic cumulonimbus-secretos -n cumulonimbus `
    --from-literal=POSTGRES_PASSWORD=$pg `
    --from-literal=DATABASE_URL="postgresql+psycopg://lluvia_app:$pg@postgres:5432/lluvia_bogota" `
    --from-literal=JWT_SECRET_KEY="$(Clave)$(Clave)"
} else { Write-Host "   cumulonimbus-secretos ya existe" }
# Un Secret creado antes de la autenticación no tiene la llave de firma de los tokens: se le agrega.
if (-not (kubectl get secret cumulonimbus-secretos -n cumulonimbus -o jsonpath="{.data.JWT_SECRET_KEY}")) {
  Write-Host "   agregando JWT_SECRET_KEY al Secret existente"
  $parche = Join-Path $env:TEMP "parche-jwt.json"
  '{"stringData":{"JWT_SECRET_KEY":"' + (Clave) + (Clave) + '"}}' | Set-Content -Path $parche -Encoding ascii
  kubectl patch secret cumulonimbus-secretos -n cumulonimbus --type merge --patch-file $parche
  Remove-Item $parche -Force
  if ($LASTEXITCODE) { throw "No se pudo agregar JWT_SECRET_KEY al Secret" }
}
if (-not (kubectl get secret grafana-admin -n monitoreo --ignore-not-found -o name)) {
  $gf = Clave
  kubectl create secret generic grafana-admin -n monitoreo --from-literal=admin-user=admin --from-literal=admin-password=$gf
  if ($LASTEXITCODE) { throw "No se pudo crear el Secret de Grafana" }
  Write-Host "   Grafana: usuario admin. Contraseña: ver README · Kubernetes y monitoreo" -ForegroundColor Yellow
} else { Write-Host "   grafana-admin ya existe" }

Write-Host "`n4. PostgreSQL ..." -ForegroundColor Cyan
kubectl apply -f k8s/10-postgres.yaml
kubectl rollout status statefulset/postgres -n cumulonimbus --timeout=300s

Write-Host "`n5. Migraciones (Job) ..." -ForegroundColor Cyan
kubectl delete job migraciones -n cumulonimbus --ignore-not-found
AplicarConImagen k8s/20-migraciones-job.yaml
kubectl wait --for=condition=complete job/migraciones -n cumulonimbus --timeout=300s

if (-not $SinMetricsServer) {
  Write-Host "`n6. metrics-server (lo necesita el autoescalado) ..." -ForegroundColor Cyan
  kubectl apply -f k8s/extras/metrics-server.yaml
}

Write-Host "`n7. API (2 réplicas), recolector y autoescalado ..." -ForegroundColor Cyan
AplicarConImagen k8s/30-api.yaml
AplicarConImagen k8s/31-recolector.yaml
kubectl apply -f k8s/40-hpa.yaml
kubectl rollout status deployment/api -n cumulonimbus --timeout=300s

Write-Host "`n8. Prometheus y Grafana ..." -ForegroundColor Cyan
kubectl apply -f k8s/monitoreo/10-prometheus.yaml -f k8s/monitoreo/20-grafana.yaml
# Para que tomen cambios del ConfigMap (configuración y dashboard) en despliegues repetidos.
kubectl rollout restart deployment/prometheus deployment/grafana -n monitoreo
kubectl rollout status deployment/grafana -n monitoreo --timeout=300s

Write-Host "`nListo. Imagen desplegada: $Imagen" -ForegroundColor Green
kubectl get pods,svc -n cumulonimbus
kubectl get pods,svc -n monitoreo
Write-Host "`nEn Docker Desktop: app http://localhost · Grafana http://localhost:3000"
Write-Host "En AKS: usa la EXTERNAL-IP de los Services api (:80) y grafana (:3000)."
Write-Host "Prometheus queda solo dentro del clúster:  kubectl port-forward svc/prometheus 9090:9090 -n monitoreo  y abrir http://localhost:9090"
Write-Host "Tráfico: python scripts/trafico.py --url http://<ip-o-localhost> --segundos 150 --usuarios 60"
