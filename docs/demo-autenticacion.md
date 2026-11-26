# Guion de la demo: contexto y autenticación

Parte de la sustentación del Proyecto 3 (unos 4 minutos: 1 de contexto y 3 de autenticación), a cargo de @SGil14.
Va antes de la demo de Kubernetes y monitoreo ([`demo-kubernetes.md`](demo-kubernetes.md)) y de la IA.

## Antes de entrar (10 minutos antes)

- [ ] La app corriendo con `JWT_SECRET_KEY` definida (en AKS o en local con `iniciar.bat`).
- [ ] **Un usuario ya registrado** (`ana@ejemplo.com`) y **otro correo libre** para registrarlo en vivo (`demo@ejemplo.com`). Si usas `ADMIN_CORREO`, ten a mano el correo del administrador.
- [ ] Una terminal con letra grande y la variable `API` apuntando a la app (`$API="http://localhost:8000"` o la IP pública de AKS).
- [ ] Pestañas abiertas: la app, `/docs` (Swagger) y el [tablero](https://github.com/users/SGil14/projects/2).
- [ ] Comprobar que `curl.exe -i $API/api/favoritos` responde `401` (la autenticación está activa).

## 1. Contexto (1 min)

Qué decir:
- «**Cumulonimbus** responde una pregunta: *¿está lloviendo donde voy?* en Bogotá, con los **71 pluviómetros del SAB/IDIGER**.»
- «El **recolector** guarda las lecturas cada 5 minutos en **PostgreSQL**; con ese histórico la app muestra cuánto llovió y se alimenta la IA.»
- «Se usa desde el **mapa web**, desde la **API** y desde un **atajo de iPhone** que dice si llueve en el destino o en la ruta.»
- «Para el Proyecto 3 sumamos: **Kubernetes en Azure**, **monitoreo con Prometheus y Grafana**, una **predicción de lluvia** y **autenticación con roles**. Cada uno tiene sus historias de usuario en el tablero» (mostrar el tablero con los sprints 4 a 6).
- «Consultar la lluvia sigue siendo **público**; la cuenta sirve para guardar favoritos y tiene dos roles.»

## 2. Registro e inicio de sesión (1 min)

En la app (mostrar que el botón dice **Entrar**):

1. Clic en **Entrar → Registrarme**. Escribir `demo@ejemplo.com` y una contraseña corta (`abc123`): el formulario avisa que faltan caracteres. Escribir una válida (`Clave1234`) → **Crear cuenta y entrar**.
2. El botón de la barra pasa a mostrar el nombre del usuario: «ya hay sesión».

Qué decir:
- «La contraseña **no se guarda**: se guarda su **hash scrypt** con una sal distinta por usuario.»
- «Al iniciar sesión la API devuelve un **token JWT** firmado, con el usuario, el **rol** y una **expiración** de 60 minutos.»
- «La **llave de firma** no está en el código: viene de la variable `JWT_SECRET_KEY`, que en Kubernetes sale de un **Secret**.»

## 3. Endpoint protegido: con y sin token (1 min)

```powershell
# Sin token: 401
curl.exe -i $API/api/favoritos

# Iniciar sesión y guardar el token
$TOKEN = (curl.exe -s -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{\"correo\":\"ana@ejemplo.com\",\"clave\":\"Clave1234\"}' | ConvertFrom-Json).access_token

# Con token: 200
curl.exe -i $API/api/favoritos -H "Authorization: Bearer $TOKEN"
```

Qué decir:
- «Sin token, `401`. Con token, `200` y **solo mis favoritos**: cada usuario ve únicamente los suyos.»
- «Un token **vencido o alterado** también da `401`» (si hay tiempo: cambiar un carácter del token y repetir).
- «Los endpoints de lluvia no piden token: la consulta sigue siendo pública» → `curl.exe -i $API/api/health/live` responde `200` sin cabecera.

En la app: escribir `Portal 80` y pulsar **☆ Guardar «Portal 80» en mis favoritos**; aparece en **Mis favoritos**. Recargar la página: la sesión y el favorito siguen ahí.

## 4. Roles (30 s)

```powershell
# Usuario normal: 403
curl.exe -i $API/api/admin/usuarios -H "Authorization: Bearer $TOKEN"
```

- «Existen dos roles: `usuario` y `administrador`. El rol viaja en el token y la API lo verifica: un usuario normal recibe **`403`** en la zona de administración.»
- Si hay tiempo: iniciar sesión con el correo del administrador y abrir **Mi cuenta** y mostrar el panel del administrador (solo él lo ve): estado del sistema, cambio de rol, favoritos de cada usuario y eliminar una cuenta.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| El registro responde `503` | Falta `JWT_SECRET_KEY` en el entorno o en el Secret. Mostrar `kubectl get secret cumulonimbus-secretos -n cumulonimbus -o jsonpath="{.data.JWT_SECRET_KEY}"` (no muestra el valor en claro) y reiniciar la API. |
| `409` al registrarse | Ese correo ya existe: usar el otro. |
| El mapa no carga lluvia | El SAB no responde (`502`); la autenticación no depende de él, seguir con la demo. |
| Sin internet | Hacer el mismo recorrido desde `/docs` contra la app local. |

## Ensayo

- [ ] Ensayado completo con cronómetro: ___ min (objetivo: 4 min o menos).
- [ ] Ensayado una vez contra el clúster de Azure, no solo en local.
