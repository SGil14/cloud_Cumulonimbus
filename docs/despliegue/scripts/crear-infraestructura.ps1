# Cumulonimbus · crea desde cero toda la infraestructura en Azure (grupo rg-cumulonimbus).
# Uso (PowerShell, con "az login" hecho y Docker Desktop abierto):
#   .\crear-infraestructura.ps1
# Requiere haber construido la imagen local con "docker compose build" en la carpeta app-completa.

$ErrorActionPreference = "Stop"

$G     = "rg-cumulonimbus"
$LOC   = "centralus"          # Azure for Students solo permite eastus, eastus2, centralus, canadacentral, mexicocentral
$SUF   = "8995"               # sufijo para los nombres que deben ser únicos en todo Azure
$PG    = "psql-cumulonimbus-$SUF"
$ACR   = "acrcumulonimbus$SUF"
$KV    = "kv-cumulonimbus-$SUF"
$ENV_  = "cae-cumulonimbus"
$APP   = "ca-cumulonimbus"
$ID    = "id-cumulonimbus"
$LOG   = "log-cumulonimbus"
$TAGS  = @("proyecto=cumulonimbus", "app=consulta-lluvia-bogota", "ambiente=produccion", "responsable=jhonAleVelasco", "curso=desarrollo-en-nube")

# Contraseña nueva de PostgreSQL (solo letras y números: va dentro de una URL)
$PW = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 28 | ForEach-Object { [char]$_ })

# 1. Grupo de recursos
az group create -n $G -l $LOC --tags $TAGS

# 2. Logs, identidad, registro de imágenes y Key Vault
az monitor log-analytics workspace create -g $G -n $LOG -l $LOC --retention-time 30 --tags proyecto=cumulonimbus componente=logs
az identity create -g $G -n $ID -l $LOC --tags proyecto=cumulonimbus componente=identidad
az acr create -g $G -n $ACR -l $LOC --sku Basic --tags proyecto=cumulonimbus componente=imagenes
az provider register -n Microsoft.KeyVault --wait
az keyvault create -g $G -n $KV -l $LOC --enable-rbac-authorization true --retention-days 7 --tags proyecto=cumulonimbus componente=secretos

# 3. PostgreSQL 16 (B1ms) con acceso solo desde servicios de Azure, y la base lluvia_bogota
az postgres flexible-server create -g $G -n $PG -l $LOC --admin-user cumulonimbus_admin --admin-password $PW `
  --sku-name Standard_B1ms --tier Burstable --version 16 --storage-size 32 --public-access 0.0.0.0 `
  --tags proyecto=cumulonimbus componente=base-de-datos --yes
az postgres flexible-server db create -g $G -s $PG -n lluvia_bogota

# 4. Permisos: la identidad descarga imágenes del ACR y lee secretos del Key Vault
$principal = az identity show -g $G -n $ID --query principalId -o tsv
$idRecurso = az identity show -g $G -n $ID --query id -o tsv
$yo        = az ad signed-in-user show --query id -o tsv
az role assignment create --assignee-object-id $principal --assignee-principal-type ServicePrincipal --role AcrPull --scope (az acr show -n $ACR --query id -o tsv)
az role assignment create --assignee-object-id $principal --assignee-principal-type ServicePrincipal --role "Key Vault Secrets User" --scope (az keyvault show -n $KV --query id -o tsv)
az role assignment create --assignee-object-id $yo --assignee-principal-type User --role "Key Vault Secrets Officer" --scope (az keyvault show -n $KV --query id -o tsv)

# 5. Secretos en Key Vault (la URL completa de la base y la contraseña sola)
$url = "postgresql+psycopg://cumulonimbus_admin:$PW@$PG.postgres.database.azure.com:5432/lluvia_bogota?sslmode=require"
az keyvault secret set --vault-name $KV -n database-url --value $url -o none
az keyvault secret set --vault-name $KV -n postgres-password --value $PW -o none

# 6. Imagen
az acr login -n $ACR
docker tag app-completa-app:latest "$ACR.azurecr.io/cumulonimbus:v1"
docker push "$ACR.azurecr.io/cumulonimbus:v1"

# 7. Entorno de Container Apps conectado a Log Analytics
$lawId  = az monitor log-analytics workspace show -g $G -n $LOG --query customerId -o tsv
$lawKey = az monitor log-analytics workspace get-shared-keys -g $G -n $LOG --query primarySharedKey -o tsv
az containerapp env create -g $G -n $ENV_ -l $LOC --environment-mode WorkloadProfiles --logs-workspace-id $lawId --logs-workspace-key $lawKey --tags proyecto=cumulonimbus componente=entorno

# 8. La aplicación (1 réplica fija para que el recolector corra cada 5 minutos)
$kvUri = az keyvault secret show --vault-name $KV -n database-url --query id -o tsv
az containerapp create -g $G -n $APP --environment $ENV_ `
  --image "$ACR.azurecr.io/cumulonimbus:v1" --user-assigned $idRecurso `
  --registry-server "$ACR.azurecr.io" --registry-identity $idRecurso `
  --target-port 8000 --ingress external --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 1 `
  --secrets "database-url=keyvaultref:$kvUri,identityref:$idRecurso" `
  --env-vars "DATABASE_URL=secretref:database-url" "RECOLECTOR_ACTIVO=true" "LOG_LEVEL=INFO" `
  --tags proyecto=cumulonimbus componente=aplicacion

az containerapp show -g $G -n $APP --query properties.configuration.ingress.fqdn -o tsv
