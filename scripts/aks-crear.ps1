# Crea el clúster AKS y el registro de imágenes (ACR) de Cumulonimbus en una suscripción de Azure,
# conecta el ACR al clúster sin contraseñas (identidad administrada, rol AcrPull) y deja kubectl apuntando a AKS.
#
# Requisitos: Azure CLI con "az login" hecho, Docker Desktop, y rol Propietario en la suscripción o en el
# grupo de recursos (hace falta para conectar el ACR al clúster).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\scripts\aks-crear.ps1 -Suscripcion "<id o nombre>"
# Después:
#   powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1 -Acr <nombre-del-acr> -SinMetricsServer
#
# Para ahorrar crédito cuando no se usa:
#   az aks stop  -g rg-cumulonimbus-k8s -n aks-cumulonimbus     # apaga los nodos (no cobra cómputo)
#   az aks start -g rg-cumulonimbus-k8s -n aks-cumulonimbus
#   az group delete -n rg-cumulonimbus-k8s --yes                # borra todo

param(
  [Parameter(Mandatory)][string]$Suscripcion,
  [string]$Region = "centralus",          # Azure for Students solo permite algunas regiones
  [string]$Grupo = "rg-cumulonimbus-k8s",
  [string]$Cluster = "aks-cumulonimbus",
  [string]$TamanoNodo = "Standard_D2s_v3",   # 2 vCPU · 8 GiB. Azure for Students solo deja tamaños con cuota (Dv3/Dv4)
  [int]$Nodos = 1
)

$ErrorActionPreference = "Stop"
function Ok($msg) { if ($LASTEXITCODE) { throw "Falló: $msg" } }

az account set --subscription $Suscripcion; Ok "seleccionar la suscripción"
$sufijo = (az account show --query id -o tsv).Substring(0, 4)   # nombres únicos y estables por suscripción
$Acr = "acrcumulonimbusk8s$sufijo"

Write-Host "`n1. Proveedores de recursos ..." -ForegroundColor Cyan
az provider register -n Microsoft.ContainerService --wait; Ok "registrar ContainerService"
az provider register -n Microsoft.ContainerRegistry --wait; Ok "registrar ContainerRegistry"

Write-Host "`n2. Grupo de recursos $Grupo ($Region) ..." -ForegroundColor Cyan
az group create -n $Grupo -l $Region --tags proyecto=cumulonimbus app=consulta-lluvia-bogota componente=kubernetes curso=desarrollo-en-nube -o none; Ok "crear el grupo"

Write-Host "`n3. Registro de imágenes $Acr ..." -ForegroundColor Cyan
az acr create -g $Grupo -n $Acr --sku Basic -l $Region --tags proyecto=cumulonimbus componente=imagenes -o none; Ok "crear el ACR"

Write-Host "`n4. Clúster AKS $Cluster ($Nodos x $TamanoNodo; tarda unos minutos) ..." -ForegroundColor Cyan
az aks create -g $Grupo -n $Cluster -l $Region `
  --tier free --node-count $Nodos --node-vm-size $TamanoNodo `
  --enable-managed-identity --generate-ssh-keys `
  --attach-acr $Acr `
  --tags proyecto=cumulonimbus componente=kubernetes -o none
Ok "crear el clúster (si falla por cuota o región, prueba otra -Region o -TamanoNodo)"

Write-Host "`n5. Credenciales de kubectl ..." -ForegroundColor Cyan
az aks get-credentials -g $Grupo -n $Cluster --overwrite-existing; Ok "obtener credenciales"
kubectl get nodes

Write-Host "`nListo. Ahora despliega la app con:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1 -Acr $Acr -SinMetricsServer"
Write-Host "Para volver al clúster local:  kubectl config use-context docker-desktop"
