# Cumulonimbus · publica una versión nueva de la app.
# Uso:  .\actualizar.ps1 -Version v2
# Ejecutar desde cualquier carpeta; construye la imagen con el Dockerfile de app-completa.

param([Parameter(Mandatory)][string]$Version)
$ErrorActionPreference = "Stop"

$G   = "rg-cumulonimbus"
$ACR = "acrcumulonimbus8995"
$APP = "ca-cumulonimbus"
$RAIZ = Join-Path $PSScriptRoot "..\..\app-completa"

az acr login -n $ACR
docker build -t "$ACR.azurecr.io/cumulonimbus:$Version" $RAIZ
docker push "$ACR.azurecr.io/cumulonimbus:$Version"
az containerapp update -g $G -n $APP --image "$ACR.azurecr.io/cumulonimbus:$Version"

$url = az containerapp show -g $G -n $APP --query properties.configuration.ingress.fqdn -o tsv
Invoke-RestMethod "https://$url/api/health"
