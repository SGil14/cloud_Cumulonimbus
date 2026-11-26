# Despliegue de Cumulonimbus en Azure

> **Versión 1 · Proyecto 2 (octubre de 2026) · retirada.** Este documento describe el primer despliegue en
> **Azure Container Apps**. Esa suscripción se quedó sin crédito y el despliegue ya no está en línea: las URL de
> abajo no responden. La versión actual corre en **Azure Kubernetes Service**; ver
> [Despliegue en Azure](../../README.md#despliegue-en-azure) y [Kubernetes y monitoreo](../../README.md#kubernetes-y-monitoreo).


**Cumulonimbus** muestra en tiempo real dónde llueve en Bogotá con los 71 pluviómetros del SAB/IDIGER.
Este documento explica cómo se desplegó en Microsoft Azure, qué recurso cumple cada función y cómo
mantenerlo.

| Dato | Valor |
|---|---|
| **App en vivo** | https://ca-cumulonimbus.greensea-2c8f82a0.centralus.azurecontainerapps.io |
| **Responsable del despliegue** | Jhon Alejandro Velasco García ([@jhonAleVelasco](https://github.com/jhonAleVelasco)) |
| **Repositorio de la app** | https://github.com/SGil14/Cumulonimbus |
| **Repositorio del curso** | https://github.com/SGil14/cloud_Cumulonimbus |
| **Suscripción** | Azure for Students |
| **Grupo de recursos** | `rg-cumulonimbus` (Central US) |
| **Fecha** | 16 de octubre de 2026 |

![La app desplegada en Azure](img/app-escritorio.png)

---

## 1. Arquitectura

![Arquitectura del despliegue](img/arquitectura.svg)

Toda la aplicación viaja en **una sola imagen de Docker** construida en dos etapas:

1. **Node 22** compila el frontend (React + Vite + MapLibre).
2. **Python 3.12** instala el backend (FastAPI) y copia el frontend ya compilado, que FastAPI sirve en `/`.

Al arrancar, el contenedor aplica las migraciones (`alembic upgrade head`) y levanta `uvicorn`.
Dentro corre también el **recolector**, que cada 5 minutos guarda las lecturas del SAB en PostgreSQL
para el historial.

## 2. Qué hay en el grupo de recursos

Todo lo de Cumulonimbus vive en **un solo grupo**, `rg-cumulonimbus`, separado de cualquier otro proyecto.
Los nombres siguen la convención de Azure `<tipo>-<proyecto>` y cada recurso tiene la etiqueta
`proyecto=cumulonimbus` y una etiqueta `componente` que dice para qué sirve.

| Recurso | Tipo | `componente` | Para qué sirve |
|---|---|---|---|
| `ca-cumulonimbus` | Container App | `aplicacion` | La app: API + frontend + recolector |
| `cae-cumulonimbus` | Entorno de Container Apps | `entorno` | Red y plataforma donde corre la app |
| `psql-cumulonimbus-8995` | PostgreSQL flexible 16 (B1ms) | `base-de-datos` | Histórico de lecturas, caché de destinos y consultas (base `lluvia_bogota`) |
| `acrcumulonimbus8995` | Container Registry (Basic) | `imagenes` | Guarda las imágenes Docker (`cumulonimbus:v1`, `v2`, …) |
| `kv-cumulonimbus-8995` | Key Vault | `secretos` | Guarda `database-url` y `postgres-password` |
| `id-cumulonimbus` | Identidad administrada | `identidad` | Permite a la app descargar la imagen y leer secretos **sin contraseñas** |
| `log-cumulonimbus` | Log Analytics | `logs` | Logs de la app (30 días) |

Etiquetas del grupo: `proyecto=cumulonimbus`, `app=consulta-lluvia-bogota`, `ambiente=produccion`,
`responsable=jhonAleVelasco`, `curso=desarrollo-en-nube`.

![Recursos del grupo](img/recursos.png)

> **Cómo encontrarlo en el portal:** [portal.azure.com](https://portal.azure.com) → *Grupos de recursos* →
> `rg-cumulonimbus`. También se puede filtrar cualquier lista del portal por la etiqueta
> `proyecto : cumulonimbus`.

## 3. Decisiones y por qué

| Decisión | Por qué |
|---|---|
| **Azure Container Apps** en vez de App Service o una VM | La app ya venía dockerizada; Container Apps corre la imagen tal cual, da HTTPS y dominio gratis y no hay servidor que administrar. |
| **1 réplica fija** (`min-replicas 1`) | El recolector debe correr cada 5 min. Con escala a cero se apagaría sin visitas y quedarían huecos en el historial. |
| **Imagen construida en local** y subida con `docker push` | Azure for Students bloquea `az acr build` (ACR Tasks). |
| **Región Central US** | La política de la suscripción solo permite eastus, eastus2, centralus, canadacentral y mexicocentral, y PostgreSQL sí tenía capacidad en centralus. |
| **Contraseña en Key Vault** y la app la lee con su identidad | La contraseña no queda en el código ni en la configuración visible de la app. El `.env` nunca se sube a git. |
| **Identidad administrada** para el registro | La app descarga su imagen sin usuario ni contraseña del ACR (rol `AcrPull`). |
| **SSL obligatorio** (`?sslmode=require`) | Azure PostgreSQL lo exige. |
| **Firewall "servicios de Azure"** (0.0.0.0) | Container Apps en plan Consumo no tiene IP de salida fija, así que no se puede limitar por IP. La base no acepta conexiones desde internet. |

## 4. Paso a paso

Todo se hizo con **Azure CLI** desde PowerShell. El script completo y repetible está en
[`scripts/crear-infraestructura.ps1`](scripts/crear-infraestructura.ps1).

### 4.1 Probar en local antes de gastar crédito

```powershell
cd app-completa
copy .env.example .env      # y poner POSTGRES_PASSWORD
docker compose up -d --build
curl http://localhost:8000/api/health
```

Resultado: `{"estado":"ok","base_datos":"ok"}`, las 71 estaciones en `/api/estaciones` y en el log
«Recolector activo cada 5 minutos» y «Histórico: 71 lecturas nuevas guardadas». No hubo que corregir nada.

### 4.2 Grupo de recursos con etiquetas

```powershell
az group create -n rg-cumulonimbus -l centralus `
  --tags proyecto=cumulonimbus app=consulta-lluvia-bogota ambiente=produccion responsable=jhonAleVelasco curso=desarrollo-en-nube
```

### 4.3 Logs, identidad, registro y Key Vault

```powershell
az monitor log-analytics workspace create -g rg-cumulonimbus -n log-cumulonimbus --retention-time 30
az identity create -g rg-cumulonimbus -n id-cumulonimbus
az acr create -g rg-cumulonimbus -n acrcumulonimbus8995 --sku Basic
az provider register -n Microsoft.KeyVault --wait
az keyvault create -g rg-cumulonimbus -n kv-cumulonimbus-8995 --enable-rbac-authorization true
```

### 4.4 PostgreSQL

```powershell
az postgres flexible-server create -g rg-cumulonimbus -n psql-cumulonimbus-8995 -l centralus `
  --admin-user cumulonimbus_admin --admin-password <generada> `
  --sku-name Standard_B1ms --tier Burstable --version 16 --storage-size 32 --public-access 0.0.0.0
az postgres flexible-server db create -g rg-cumulonimbus -s psql-cumulonimbus-8995 -n lluvia_bogota
```

### 4.5 Permisos y secretos

```powershell
# La identidad de la app: descargar imágenes y leer secretos
az role assignment create --assignee-object-id <principalId> --role AcrPull --scope <id del ACR>
az role assignment create --assignee-object-id <principalId> --role "Key Vault Secrets User" --scope <id del Key Vault>

# La URL de conexión completa queda como secreto
az keyvault secret set --vault-name kv-cumulonimbus-8995 -n database-url `
  --value "postgresql+psycopg://cumulonimbus_admin:<password>@psql-cumulonimbus-8995.postgres.database.azure.com:5432/lluvia_bogota?sslmode=require"
```

### 4.6 Imagen

```powershell
az acr login -n acrcumulonimbus8995
docker tag app-completa-app:latest acrcumulonimbus8995.azurecr.io/cumulonimbus:v1
docker push acrcumulonimbus8995.azurecr.io/cumulonimbus:v1
```

### 4.7 Entorno y aplicación

```powershell
az containerapp env create -g rg-cumulonimbus -n cae-cumulonimbus -l centralus --environment-mode WorkloadProfiles `
  --logs-workspace-id <customerId> --logs-workspace-key <clave>

az containerapp create -g rg-cumulonimbus -n ca-cumulonimbus --environment cae-cumulonimbus `
  --image acrcumulonimbus8995.azurecr.io/cumulonimbus:v1 `
  --user-assigned <id de id-cumulonimbus> `
  --registry-server acrcumulonimbus8995.azurecr.io --registry-identity <id de id-cumulonimbus> `
  --target-port 8000 --ingress external --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 1 `
  --secrets "database-url=keyvaultref:<uri del secreto>,identityref:<id de id-cumulonimbus>" `
  --env-vars "DATABASE_URL=secretref:database-url" "RECOLECTOR_ACTIVO=true" "LOG_LEVEL=INFO"
```

## 5. Evidencia en el portal de Azure

Capturas reales del portal ([portal.azure.com](https://portal.azure.com)) después del despliegue. Se taparon
la IP pública del equipo y los datos de otras personas con acceso heredado a la suscripción.

### 5.1 Grupo de recursos y creación

**Grupo `rg-cumulonimbus`**: los 7 recursos en Central US y las etiquetas del proyecto.

![Grupo de recursos](img/portal/01-grupo-recursos.png)

**Registro de actividad**: cada operación de creación (`Create or Update Container App`,
`Create or Update Managed Environment`, `Update PostgreSQL server Create`, `Create or Update Container Registry`,
`Update Key Vault`, `Update User Assigned Identity Create`, …) hecha desde Azure CLI con la cuenta del responsable.
Las filas en rojo son intentos fallidos durante la configuración, por ejemplo el primer intento de crear la app en
el entorno *express* (sección 10). Se corrigieron y la operación siguiente terminó bien.

![Registro de actividad](img/portal/02-registro-actividad.png)

### 5.2 La aplicación: `ca-cumulonimbus`

**Información general**: en ejecución, URL pública, entorno `cae-cumulonimbus` con perfiles de carga de trabajo,
Log Analytics conectado y etiquetas.

![Container App](img/portal/03-app-informacion.png)

**Contenedor**: la imagen `cumulonimbus:v1` sale de `acrcumulonimbus8995` y se descarga con la identidad
administrada `id-cumulonimbus`, sin usuario ni contraseña.

![Contenedor](img/portal/04-app-contenedor.png)

**Variables de entorno**: `DATABASE_URL` no tiene el valor escrito; *hace referencia al secreto* `database-url`,
que viene de Key Vault.

![Variables de entorno](img/portal/04b-app-variables.png)

**Entrada (ingress)**: tráfico desde cualquier lugar, HTTP, puerto 8000, sin conexiones inseguras (solo HTTPS).

![Ingress](img/portal/06-app-ingress.png)

**Escala**: mínimo 1 y máximo 1 réplica, para que el recolector corra siempre.

![Escala](img/portal/07-app-escalado.png)

**Revisiones**: la revisión activa recibe el 100 % del tráfico. Cada versión nueva crea una revisión y Azure pasa el tráfico cuando la nueva está lista, sin cortar el servicio.

![Revisiones](img/portal/09-app-revisiones.png)

**Secuencia de registro (en vivo)**: el recolector consulta el SAB cada 5 minutos
(«SAB: 71 estaciones recibidas», «Histórico: 65 lecturas nuevas guardadas») y responde `/api/health`.

![Logs en vivo](img/portal/10-app-registros.png)

### 5.3 Entorno: `cae-cumulonimbus`

![Entorno](img/portal/11-entorno.png)

### 5.4 Base de datos: `psql-cumulonimbus-8995`

**Información general**: PostgreSQL 16.15, Burstable B1ms (1 vCore, 2 GiB, 32 GiB), administrador
`cumulonimbus_admin`.

![PostgreSQL](img/portal/12-postgres-informacion.png)

**Redes**: TLS/SSL obligatorio y acceso solo desde servicios de Azure; no hay reglas para IPs de internet.

![Redes de PostgreSQL](img/portal/13-postgres-redes.png)

**Bases de datos**: `lluvia_bogota` junto a las bases del sistema.

![Bases de datos](img/portal/14-postgres-bases.png)

### 5.5 Registro de imágenes, secretos e identidad

**`acrcumulonimbus8995` → Repositorios**: el repositorio `cumulonimbus`.

![Container Registry](img/portal/15-acr-repositorios.png)

**`kv-cumulonimbus-8995` → Secretos**: `database-url` y `postgres-password`.

![Key Vault secretos](img/portal/16-keyvault-secretos.png)

**`kv-cumulonimbus-8995` → Control de acceso**: el responsable es *Agente de secretos* (puede escribirlos) y
`id-cumulonimbus` es *Usuario de secretos* (solo puede leerlos).

![Key Vault permisos](img/portal/17-keyvault-permisos.png)

**`id-cumulonimbus` → Asignaciones de roles**: `AcrPull` sobre el registro y `Usuario de secretos de Key Vault`
sobre el almacén. Son los dos únicos permisos que tiene la app.

![Roles de la identidad](img/portal/18-identidad-roles.png)

## 6. Verificación

| Prueba | Resultado |
|---|---|
| `GET /api/health` | `{"estado":"ok","base_datos":"ok"}` |
| `GET /` (frontend) | 200 |
| `GET /api/estaciones` | 71 estaciones del SAB |
| `GET /api/destino?q=Chapinero` | 200 (escribe en `geocache` y `consultas`) |
| `GET /api/historial/serie?periodo=6h` | 200 (lee el histórico que guarda el recolector) |
| `GET /api/atajo?q=Chapinero` (v2) | 200: «No llueve cerca de Chapinero. Ninguna estación cercana registra lluvia ahora.» |
| `GET /api/atajo/ruta?origen=…&destino=…&modo=…` (v2) | 200 |
| Secreto de la base | Se lee desde Key Vault (`keyvaultref`) con la identidad `id-cumulonimbus` |
| SSL en PostgreSQL | `require_secure_transport = on` |

![Verificación desde la terminal](img/verificacion.png)

La app también se adapta al celular: el panel pasa a ser una hoja inferior.

<img src="img/app-celular.png" alt="Cumulonimbus en celular" width="300">

## 7. Historial de versiones

| Versión | Fecha | Revisión | Qué cambió |
|---|---|---|---|
| `v1` | 16/10/2026 11:20 | `ca-cumulonimbus--ti6pcxy` | Primer despliegue (commit `7355dd0` de [SGil14/Cumulonimbus](https://github.com/SGil14/Cumulonimbus)). |
| `v2` | 16/10/2026 18:30 | `ca-cumulonimbus--0000001` | Atajo de iPhone: endpoints `/api/atajo` y `/api/atajo/ruta`, y README definitivo (commit `d92f9a5`). Sin cambios de infraestructura, variables ni migraciones. |

Las capturas del portal de la sección 5 son de la `v1`; la configuración de la `v2` es la misma, solo cambia la imagen.

## 8. Actualizar la app

Con el script [`scripts/actualizar.ps1`](scripts/actualizar.ps1):

```powershell
.\scripts\actualizar.ps1 -Version v2
```

Este script construye la imagen, la sube con la etiqueta nueva, cambia la Container App a esa imagen y
consulta `/api/health`. Hay que subir el número de versión en cada despliegue (v2, v3, …) para poder
volver atrás si algo falla:

```powershell
az containerapp update -g rg-cumulonimbus -n ca-cumulonimbus --image acrcumulonimbus8995.azurecr.io/cumulonimbus:v1
```

## 9. Ver logs y estado

- **Portal:** `ca-cumulonimbus` → *Supervisión* → *Secuencia de registro* (en vivo) o *Registros* (Log Analytics).
- **CLI:**

```powershell
az containerapp show -g rg-cumulonimbus -n ca-cumulonimbus --query "{estado:properties.runningStatus,imagen:properties.template.containers[0].image}" -o table
az containerapp revision list -g rg-cumulonimbus -n ca-cumulonimbus -o table
```

Consulta útil en *Registros* de `log-cumulonimbus`:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "ca-cumulonimbus"
| where Log_s has "Histórico"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

## 10. Problemas que encontramos y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| `SSL certificate problem: unable to get local issuer certificate` en git y en Azure CLI | El **escudo web de AVG Antivirus** intercepta HTTPS con su propio certificado | Git: `git -c http.sslBackend=schannel clone …` (usa los certificados de Windows). Azure CLI: un paquete de certificados con la raíz de AVG, indicado en `REQUESTS_CA_BUNDLE`. |
| `az containerapp …` falla con `Acceso denegado` | La extensión `containerapp` quedó dañada en `~/.azure/cliextensions` | Instalarla en otra carpeta: `$env:AZURE_EXTENSION_DIR="C:\ruta\nueva"; az extension add -n containerapp` |
| `--registry-identity must be an identity resource ID` | Git Bash convierte los textos que empiezan con `/` en rutas de Windows | `MSYS_NO_PATHCONV=1` o usar PowerShell |
| `MissingSubscriptionRegistration … Microsoft.KeyVault` | La suscripción nunca había usado Key Vault | `az provider register -n Microsoft.KeyVault --wait` |
| `--database-name … only applies to elastic clusters` | Cambio en Azure CLI 2.90 | Crear el servidor primero y la base después con `az postgres flexible-server db create` |
| `'KeyVaultUrl in secrets' is not supported … on express environments` | La extensión en preview crea por defecto entornos *express*, que no admiten Key Vault | Crear el entorno con `--environment-mode WorkloadProfiles` (perfil de consumo, mismo costo) |
| Docker Desktop no arranca: `initializing Ingest server … rename sailor-ingest.sock` | Docker Desktop se abrió desde una terminal con permisos restringidos y no pudo renombrar un archivo interno | Cerrar Docker Desktop y abrirlo normal desde Windows. **No** usar «Reset to factory defaults», que borra imágenes y volúmenes. |

## 11. Costos

Valores aproximados con precios de lista de Central US:

| Recurso | Costo aproximado al mes |
|---|---|
| PostgreSQL B1ms + 32 GB | ~ 16 USD (cobra las 24 horas, aunque nadie use la app) |
| Container Registry Basic | ~ 5 USD |
| Container App (0,5 vCPU, 1 réplica) | Pocos dólares; la mayor parte del tiempo está inactiva y la cubre la cuota gratis |
| Key Vault, identidad, Log Analytics | Céntimos |

**Para pausar sin borrar:**

```powershell
az postgres flexible-server stop -g rg-cumulonimbus -n psql-cumulonimbus-8995   # Azure la vuelve a encender a los 7 días
az containerapp update -g rg-cumulonimbus -n ca-cumulonimbus --min-replicas 0
```

**Para borrar todo al terminar la materia** (no se puede deshacer):

```powershell
az group delete -n rg-cumulonimbus --yes --no-wait
```
