# Cumulonimbus - Gestión Colaborativa

**¿Está lloviendo donde voy a estar?** Cumulonimbus consulta en vivo los pluviómetros del SAB / IDIGER de Bogotá y te lo dice en una frase: dónde llueve ahora, si llueve cerca de un destino, si te va a mojar en tu ruta y cuánto ha llovido antes. Todo sobre un mapa, en el celular o en el computador, y con un histórico propio guardado en PostgreSQL para analizar la lluvia con el tiempo.

![Cumulonimbus con el diseño Clima, tema claro](docs/img/01-diseno-clima-claro.png)

> **Sobre las capturas de este documento.** Cuando se tomaron las capturas casi no llovía en Bogotá, así que las imágenes que muestran lluvia (zonas de color, radar encendido, el panel «7 de 71») usan **estaciones y ecos de radar simulados** para poder enseñar cómo se ve. Las imágenes del buscador, la ruta, el historial y la documentación de la API usan **datos reales** del momento de la captura. Las capturas del atajo de iPhone son de un **teléfono real**.

---

## Contenido

1. [Equipo de Desarrollo](#equipo-de-desarrollo)
2. [Descripción del Proyecto](#descripción-del-proyecto)
3. [Arquitectura](#arquitectura)
4. [Metodología y Gestión del Proyecto](#metodología-y-gestión-del-proyecto)
5. [Sprints](#sprints)
6. [Métricas del Proyecto](#métricas-del-proyecto)
7. [Instalación y Uso](#instalación-y-uso)
8. [Documentación de la API](#documentación-de-la-api)
9. [Autenticación y roles](#autenticación-y-roles)
10. [Atajo para iPhone](#atajo-para-iphone)
11. [Base de datos](#base-de-datos)
12. [Reglas y cálculos](#reglas-y-cálculos)
13. [Los cinco diseños](#los-cinco-diseños)
14. [Estructura del proyecto](#estructura-del-proyecto)
15. [Pruebas](#pruebas)
16. [Despliegue en Azure](#despliegue-en-azure)
17. [Kubernetes y monitoreo](#kubernetes-y-monitoreo)
18. [Inteligencia artificial](#inteligencia-artificial)
19. [Construir, desplegar y correr todo el stack](#construir-desplegar-y-correr-todo-el-stack)
20. [Límites que debes conocer](#límites-que-debes-conocer)
21. [Solución de problemas](#solución-de-problemas)
22. [Mejoras futuras](#mejoras-futuras)
23. [Fuentes de datos y créditos](#fuentes-de-datos-y-créditos)
24. [Enlaces importantes](#enlaces-importantes)

---

## Equipo de Desarrollo

Proyecto del curso **Desarrollo de Aplicaciones en la Nube · Proyecto 2** (gestión colaborativa con GitHub Projects). Equipo de 3 personas, **sin roles fijos**: cada integrante puede tomar historias de cualquier área (Frontend, Backend, DevOps, QA). Quien lidera el proyecto es el Product Owner, que prioriza el backlog y es quien **acepta** las historias terminadas.

| Rol | Integrante | Usuario de GitHub | Responsabilidad |
|---|---|---|---|
| **Product Owner** | Sebastian Gil Marin | [@SGil14](https://github.com/SGil14) | Prioriza el backlog, define y valida los criterios de aceptación y acepta cada historia en la columna *Review* antes de pasarla a *Done*. Además desarrolla 11 historias (HU-03, 04, 05, 07, 09, 10, 21, 24, 26, 27, 28) y se encarga de la documentación (HU-26). |
| Desarrollador | Ian Cardona | [@iancardonag](https://github.com/iancardonag) | Desarrolla 8 historias (HU-02, 06, 08, 14, 17, 18, 23, 25) en backend, frontend y pruebas. |
| Desarrollador y responsable del despliegue | Jhon Alejandro Velasco García | [@jhonAleVelasco](https://github.com/jhonAleVelasco) | Desarrolla 9 historias (HU-01, 11, 12, 13, 15, 16, 19, 20, 22) y se encarga del **despliegue en Azure** (ver «Despliegue en Azure»). |

---

## Descripción del Proyecto

### ¿Para qué sirve?

El IDIGER (Instituto Distrital de Gestión de Riesgos y Cambio Climático) mantiene en Bogotá una red de **71 pluviómetros** que reportan cuánta lluvia cae, cada pocos minutos. Esos datos son públicos en la página del SAB, pero están pensados para consultarse estación por estación. Cumulonimbus los convierte en respuestas:

| Pregunta | Qué responde la app |
|---|---|
| ¿Está lloviendo en Bogotá? | Cuántas de las 71 estaciones registran lluvia y en qué localidades. |
| ¿Llueve donde voy? | Escribes un barrio, lugar, dirección, esquina o coordenadas y te dice si llueve cerca, con las 3 estaciones más próximas. |
| ¿Me voy a mojar en el camino? | Calculas una ruta de un lugar a otro y la app marca los tramos donde llueve. |
| ¿Cuánto llovió antes? | Historial por horas o por días, para toda Bogotá, una localidad o un destino. |
| ¿De dónde viene la lluvia? | Capa opcional del radar meteorológico del IDIGER. |

**Solo consulta cuando tú se lo pides**: no se actualiza sola. Se actualiza al abrirla o al pulsar «Actualizar». (El histórico sí se llena solo mientras el servidor está encendido; ver [Recolector](#recolector-del-histórico).)

### Qué puedes hacer con la app

#### Ver dónde llueve ahora

Al abrir la app, el panel superior responde en una frase («Bogotá está seca» o «7 de 71 estaciones registran lluvia») y debajo lista las localidades donde llueve. En el mapa cada estación es un punto: los que están **secos** son puntos pequeños; los que **registran lluvia** se agrandan, se rodean de ondas y toman el color de su intensidad.

![Zonas de lluvia alrededor de cada estación](docs/img/11-zonas-de-lluvia.png)

**Colores de la intensidad (mm/h):**

| Color | Intensidad | Cuánto llueve |
|---|---|---|
| Azul / celeste | Ligera | menos de 2,5 mm/h |
| Amarillo | Moderada | de 2,5 a 7,6 mm/h |
| Naranja | Fuerte | de 7,6 a 50 mm/h |
| Rojo | Muy fuerte | 50 mm/h o más |

Alrededor de cada estación que llueve se pinta además una **zona de color difuminada** (de unos 2,5 km de radio en la lluvia ligera a unos 5,5 km en la muy fuerte). Es una estimación visual de la zona que cubre la medición: el pluviómetro mide un solo punto. La zona se desvanece al acercar el mapa para no taparlo.

Al tocar una estación aparece su ficha con intensidad actual, acumulado del día y hora de la última lectura.

#### Consultar un destino

Escribe en el buscador cualquiera de estas cosas:

- Una **localidad**: `Chapinero`
- **Coordenadas**: `4.6486, -74.0628`
- Un **barrio o lugar**: `Portal 80`, `Galerías`
- Una **dirección**: `Carrera 7 # 55-25`
- Una **esquina**: `Calle 72 con Carrera 10`, `Av Boyacá con Calle 80`

![Resultado de buscar una esquina](docs/img/07-buscar-destino.png)

La respuesta dice con claridad si llueve cerca («Sí, llueve cerca» o «No llueve cerca»), indica el barrio y la localidad, y lista las **3 estaciones más cercanas** con su distancia, su estado y lo que han acumulado hoy. Si la app no encontró el número exacto de la dirección y usó la placa más cercana de la misma cuadra, te avisa que la ubicación es **aproximada**. El enlace «Ver cuándo ha llovido aquí» abre el historial de ese punto.

#### Revisar una ruta (¿me mojo en el camino?)

Debajo del buscador está **«¿Vas de un lugar a otro? Revisa la ruta»**. Escribes el origen y el destino, eliges cómo te mueves (carro/moto, bus, bici o a pie) y la app dibuja el trayecto y lo colorea por tramos: **lluvia**, **seco** o **sin datos**.

![Ruta de Portal 80 a Calle 72 con Carrera 10](docs/img/09-ruta.png)

El panel resume distancia, duración y en qué kilómetros llueve, con una barra de salida a llegada. Detalles importantes:

- Muestra la lluvia **de ahora**, no la que habrá cuando llegues a cada punto.
- Un tramo queda **«sin datos»** si la estación más cercana está a más de 4 km o su última lectura es vieja. No se asume que está seco.

#### Ver el historial de lluvia

El botón **«Historial»** de la barra abre una ventana con cuánto llovió y cuándo.

![Historial de lluvia de las últimas 24 horas](docs/img/08-historial.png)

- **Periodos:** 6 horas, 24 horas (barras por hora), 7 días y 30 días (barras por día).
- **Dónde:** toda Bogotá, una localidad o «cerca de tu destino» (con las 3 estaciones más próximas a elegir).
- **Indicadores:** total llovido, hora o día más lluvioso y porcentaje de datos disponibles.
- **Ranking** de las localidades más lluviosas del periodo; al pulsar una, el gráfico pasa a esa localidad.
- Los intervalos en los que la app estaba apagada aparecen como **«sin datos»**: no se inventa lluvia ni se supone que no llovió.

#### Radar meteorológico (opcional)

El botón **«Radar»** superpone la imagen de reflectividad del radar del IDIGER, la misma capa de la página del SAB.

![Radar encendido sobre el mapa](docs/img/10-radar-encendido.png)

Hay que entenderlo bien, porque **el radar mide lluvia en el aire, no en el suelo**. Puede mostrar gotas que se evaporan antes de llegar o no mostrar una llovizna muy fina. Por eso:

- Está **apagado por defecto** (la app recuerda lo que elijas).
- Cuando lo enciendes, **solo dibuja los ecos de lluvia moderada o más fuerte** (amarillo, naranja, rojo). La llovizna y los ecos débiles (verde, cian, azul), y el blanco o los tonos pálidos, se descartan.
- En el tema claro los colores se oscurecen un poco (dorado, naranja vivo, carmesí) y llevan un borde oscuro para que no se pierdan sobre el fondo.
- La leyenda dice «Radar · lluvia en el aire» con la hora de la imagen.
- Sirve para ver lluvia **entre** estaciones y **fuera** de la ciudad, y de dónde viene. Para decir «llueve aquí» mandan siempre los pluviómetros.

#### Cinco diseños, tema claro y oscuro, celular y computador

El botón **«Diseño»** cambia entre cinco estilos visuales y la app recuerda el último. El botón de la luna/sol cambia entre tema claro y oscuro. Funciona igual en computador y en celular: en el celular el panel se vuelve una hoja que sube desde abajo.

![Cumulonimbus en el celular](docs/img/12-celular.png)

Los cinco diseños están descritos en la [Los cinco diseños](#los-cinco-diseños).

---

## Arquitectura

### Arquitectura

```mermaid
flowchart LR
    subgraph Fuentes["Fuentes externas (gratuitas)"]
        SAB["SAB / IDIGER<br/>pluviómetros"]
        KMZ["Radar IDIGER<br/>(KMZ)"]
        CAT["Catastro Bogotá<br/>(direcciones, barrios)"]
        NOM["Nominatim<br/>(OpenStreetMap)"]
        VAL["Valhalla<br/>(rutas)"]
    end

    subgraph Backend["Backend · FastAPI (Python)"]
        API["API /api/*"]
        SRV["Servicios<br/>lluvia, geocodificación,<br/>historial, ruta, radar"]
        REC["Recolector<br/>cada 5 min"]
        CACHE["Caché en memoria"]
    end

    DB[("PostgreSQL<br/>estaciones · lecturas<br/>geocache · consultas")]
    FRONT["Frontend · React + MapLibre<br/>(servido por el mismo backend)"]

    SAB --> SRV
    KMZ --> SRV
    CAT --> SRV
    NOM --> SRV
    VAL --> SRV
    SRV <--> CACHE
    REC --> SAB
    REC --> DB
    SRV <--> DB
    API --> SRV
    FRONT <-->|JSON| API
```

### Qué pasa cuando abres la app

1. El navegador carga el frontend (React) y pide al backend `/api/resumen`, `/api/estaciones`, `/api/localidades` y `/api/radar`.
2. El backend consulta al SAB (`POST https://app.sab.gov.co/sab/ServletTipoSensores`, sensores de tipo 5 = pluviómetro). Guarda la respuesta **90 segundos** en memoria para no saturar al SAB si varias personas consultan a la vez.
3. Cada vez que trae datos frescos, **guarda una foto** (snapshot) de las lecturas en PostgreSQL. Así el histórico se llena también con las consultas de los usuarios.
4. Clasifica cada estación (intensidad, acumulado, si la lectura es vieja) y arma el resumen por localidad.
5. El frontend dibuja el mapa. No hay mapa base de calles: solo el contorno de las localidades y las estaciones.

### Recolector del histórico

El backend arranca con un **recolector** (APScheduler) que cada **5 minutos** consulta el SAB y guarda las lecturas en PostgreSQL, aunque nadie tenga la app abierta. La tabla `lecturas` tiene una restricción única por `(id_sensor, fecha_lectura)`, así que una misma lectura nunca se guarda dos veces. Se controla con `RECOLECTOR_ACTIVO` y `RECOLECTOR_INTERVALO_MINUTOS`.

> El histórico solo se llena **mientras el servidor está encendido**. Si lo apagas, esas horas quedan como «sin datos».

### Tecnologías

| Parte | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, psycopg 3, Alembic (migraciones), pydantic-settings, APScheduler, httpx |
| Base de datos | PostgreSQL (probado con la 18) |
| Frontend | React 19, Vite, TypeScript, MapLibre GL 5 |
| Pruebas | pytest |

Todos los servicios externos que usa son **gratuitos y no necesitan clave**.

---

## Metodología y Gestión del Proyecto

Se trabaja con **Kanban** sobre un [GitHub Project](https://github.com/users/SGil14/projects/2) vinculado a este repositorio ([SGil14/cloud_Cumulonimbus](https://github.com/SGil14/cloud_Cumulonimbus)), simulando **3 sprints**.

### Tablero Kanban

```
Backlog  →  Ready  →  In Progress  →  Review  →  Done
```

| Columna | Qué significa | Quién actúa |
|---|---|---|
| **Backlog** | Historias por ordenar. | Product Owner |
| **Ready** | Historia clara, estimada y priorizada: lista para empezar. | Product Owner |
| **In Progress** | Alguien la tiene asignada y está trabajando en ella. | Responsable |
| **Review** | Pull request abierto: otro integrante revisa el código y el Product Owner comprueba los criterios de aceptación. | Revisor y Product Owner |
| **Done** | Aceptada por el Product Owner y fusionada. | Product Owner |

### Campos personalizados

| Campo | Valores |
|---|---|
| **Sprint** | Sprint 1, Sprint 2, Sprint 3 |
| **Responsable** | El miembro asignado (campo *Assignees* de GitHub) |
| **Prioridad** | Alta, Media, Baja |
| **Estimación** | Puntos de historia: 1, 2, 3, 5, 8 |
| **Tipo** | Feature, Bug, Documentation, DevOps, Testing |

Además se usan etiquetas: `historia`, `bug`, área (`backend`, `frontend`, `datos`, `infra`), tamaño original (`tamaño:S/M/L`) y una por épica.

### Historias de usuario

Cada historia sigue esta plantilla (ver cualquier issue `HU-xx` del repositorio):

```
# Historia de Usuario: [Título]

## Como [tipo de usuario]
Quiero [funcionalidad]
Para [beneficio/valor]

## Criterios de Aceptación:
- [ ] Criterio 1
- [ ] Criterio 2

## Estimación: [puntos]
## Sprint: [número]
## Responsable: @[username]
```

El backlog tiene **28 historias** (HU-01 a HU-28), organizadas en **9 épicas**:

| Épica | Tema |
|---|---|
| E1 · Datos y base del sistema | Lectura del SAB, clasificación, PostgreSQL, recolector, configuración |
| E2 · Consulta de lluvia | Resumen, fichas de estación, acumulado por localidad, actualización |
| E3 · Mapa | Mapa sin mapa base, colores por intensidad, zonas de lluvia |
| E4 · Búsqueda de destinos | Localidades, coordenadas, direcciones, barrios y lugares, caché |
| E5 · Ruta | Lluvia a lo largo de un trayecto |
| E6 · Historial | Gráficos por hora y por día, ranking |
| E7 · Radar | Capa del radar meteorológico |
| E8 · Diseño y experiencia | Cinco diseños, temas, celular, lluvia animada |
| E9 · Calidad y entrega | Pruebas, documentación, Docker, repositorio |

Además hay **13 bugs** documentados como issues cerrados (BUG-01 a BUG-13): defectos encontrados y corregidos durante el desarrollo inicial.

### Estrategia de ramas

```
main
├── production            (despliegue)
└── development           (desarrollo)
    ├── feature/sprint1-[funcionalidad]
    ├── feature/sprint2-[funcionalidad]
    └── feature/sprint3-[funcionalidad]
```

Flujo de trabajo:

1. Crear una rama `feature/sprintN-…` desde `development`.
2. Desarrollar la funcionalidad y hacer commits frecuentes con mensajes descriptivos.
3. Abrir un **Pull Request** con revisión obligatoria de otro integrante.
4. Fusionar en `development`.
5. Probar en `development`.
6. Publicar en `production` (despliegue).

### Automatización

| Automatización | Estado |
|---|---|
| Mover la tarjeta a *In Progress* al asignar el issue y a *Done* al fusionar el PR (GitHub Actions) | Pendiente |
| Integración continua: pruebas del backend y compilación del frontend en cada PR (GitHub Actions) | Pendiente |
| Automatizaciones nativas del GitHub Project (cerrar issue, PR vinculado, PR fusionado) | Disponibles, por activar |

### Evidencias que se irán recogiendo

- [ ] Capturas del tablero Kanban en distintos estados.
- [ ] Logs de commits de los tres integrantes.
- [ ] Pull requests con code reviews.
- [ ] Capturas de la aplicación funcionando.
- [ ] Evidencia de participación equitativa.

---

## Sprints

> Las 28 historias están **fusionadas en `main`** mediante tres Pull Requests, uno por integrante ([#42](https://github.com/SGil14/cloud_Cumulonimbus/pull/42), [#43](https://github.com/SGil14/cloud_Cumulonimbus/pull/43) y [#44](https://github.com/SGil14/cloud_Cumulonimbus/pull/44)), con un commit por historia. El detalle de cada historia, con sus criterios de aceptación, está en el [tablero](https://github.com/users/SGil14/projects/2).

### Sprint 1 · Backend y base de datos
**Objetivo:** leer los pluviómetros del SAB, clasificar la lluvia, guardar el histórico y resolver destinos. **9 historias · 30 puntos.**

| Historia | Título | Puntos | Prioridad | Tipo | Responsable | Estado |
|---|---|---|---|---|---|---|
| [HU-01](https://github.com/SGil14/cloud_Cumulonimbus/issues/1) | Consultar los pluviómetros del SAB | 5 | Alta | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-02](https://github.com/SGil14/cloud_Cumulonimbus/issues/2) | Clasificar la lluvia | 2 | Alta | Feature | @iancardonag | Hecho · PR #44 |
| [HU-03](https://github.com/SGil14/cloud_Cumulonimbus/issues/3) | Guardar el histórico en PostgreSQL | 5 | Alta | Feature | @SGil14 | Hecho · PR #42 |
| [HU-04](https://github.com/SGil14/cloud_Cumulonimbus/issues/4) | Recolector automático cada 5 minutos | 2 | Alta | Feature | @SGil14 | Hecho · PR #42 |
| [HU-05](https://github.com/SGil14/cloud_Cumulonimbus/issues/5) | Configuración por variables de entorno | 1 | Media | DevOps | @SGil14 | Hecho · PR #42 |
| [HU-13](https://github.com/SGil14/cloud_Cumulonimbus/issues/13) | Consultar por localidad o coordenadas | 2 | Alta | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-14](https://github.com/SGil14/cloud_Cumulonimbus/issues/14) | Buscar direcciones y esquinas de Bogotá | 8 | Alta | Feature | @iancardonag | Hecho · PR #44 |
| [HU-15](https://github.com/SGil14/cloud_Cumulonimbus/issues/15) | Buscar barrios y lugares | 3 | Media | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-16](https://github.com/SGil14/cloud_Cumulonimbus/issues/16) | Caché de destinos y registro de consultas | 2 | Media | Feature | @jhonAleVelasco | Hecho · PR #43 |

- Evidencias: commits `HU-xx` de cada Pull Request y los issues cerrados en el tablero.

### Sprint 2 · Frontend
**Objetivo:** mapa, panel de resultados, estaciones, buscador y experiencia visual. **11 historias · 36 puntos.**

| Historia | Título | Puntos | Prioridad | Tipo | Responsable | Estado |
|---|---|---|---|---|---|---|
| [HU-06](https://github.com/SGil14/cloud_Cumulonimbus/issues/6) | Ver cuántas estaciones registran lluvia | 3 | Alta | Feature | @iancardonag | Hecho · PR #44 |
| [HU-07](https://github.com/SGil14/cloud_Cumulonimbus/issues/7) | Ficha de cada estación | 1 | Media | Feature | @SGil14 | Hecho · PR #42 |
| [HU-08](https://github.com/SGil14/cloud_Cumulonimbus/issues/8) | Lluvia acumulada por localidad | 2 | Media | Feature | @iancardonag | Hecho · PR #44 |
| [HU-09](https://github.com/SGil14/cloud_Cumulonimbus/issues/9) | Actualizar a demanda | 1 | Media | Feature | @SGil14 | Hecho · PR #42 |
| [HU-10](https://github.com/SGil14/cloud_Cumulonimbus/issues/10) | Mapa de Bogotá sin mapa base | 5 | Alta | Feature | @SGil14 | Hecho · PR #42 |
| [HU-11](https://github.com/SGil14/cloud_Cumulonimbus/issues/11) | Estaciones coloreadas por intensidad | 2 | Alta | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-12](https://github.com/SGil14/cloud_Cumulonimbus/issues/12) | Zonas de color alrededor de cada estación | 3 | Media | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-17](https://github.com/SGil14/cloud_Cumulonimbus/issues/17) | Respuesta «¿llueve cerca?» | 5 | Alta | Feature | @iancardonag | Hecho · PR #44 |
| [HU-22](https://github.com/SGil14/cloud_Cumulonimbus/issues/22) | Cinco diseños intercambiables | 8 | Baja | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-23](https://github.com/SGil14/cloud_Cumulonimbus/issues/23) | Tema claro/oscuro y versión celular | 3 | Media | Feature | @iancardonag | Hecho · PR #44 |
| [HU-24](https://github.com/SGil14/cloud_Cumulonimbus/issues/24) | Lluvia animada (Mapa vivo) | 3 | Baja | Feature | @SGil14 | Hecho · PR #42 |

- Evidencias: commits `HU-xx` de cada Pull Request y los issues cerrados en el tablero.

### Sprint 3 · Funciones avanzadas, calidad y despliegue
**Objetivo:** ruta, historial y radar, pruebas, documentación, Docker y despliegue en la nube. **8 historias · 38 puntos.**

| Historia | Título | Puntos | Prioridad | Tipo | Responsable | Estado |
|---|---|---|---|---|---|---|
| [HU-18](https://github.com/SGil14/cloud_Cumulonimbus/issues/18) | Revisar la lluvia en una ruta | 8 | Media | Feature | @iancardonag | Hecho · PR #44 |
| [HU-19](https://github.com/SGil14/cloud_Cumulonimbus/issues/19) | Gráfico de lluvia por hora y por día | 8 | Media | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-20](https://github.com/SGil14/cloud_Cumulonimbus/issues/20) | Ranking de localidades más lluviosas | 2 | Baja | Feature | @jhonAleVelasco | Hecho · PR #43 |
| [HU-21](https://github.com/SGil14/cloud_Cumulonimbus/issues/21) | Capa del radar meteorológico | 8 | Media | Feature | @SGil14 | Hecho · PR #42 |
| [HU-25](https://github.com/SGil14/cloud_Cumulonimbus/issues/25) | Pruebas automáticas del backend | 5 | Media | Testing | @iancardonag | Hecho · PR #44 |
| [HU-26](https://github.com/SGil14/cloud_Cumulonimbus/issues/26) | Documentación del proyecto | 3 | Alta | Documentation | @SGil14 | Hecho · PR #42 |
| [HU-27](https://github.com/SGil14/cloud_Cumulonimbus/issues/27) | Docker | 3 | Alta | DevOps | @SGil14 | Hecho · PR #42 |
| [HU-28](https://github.com/SGil14/cloud_Cumulonimbus/issues/28) | Repositorio y nombre del proyecto | 1 | Media | DevOps | @SGil14 | Hecho · PR #42 |

- Evidencias: commits `HU-xx` de cada Pull Request y los issues cerrados en el tablero.

---

## Métricas del Proyecto

Las métricas se calculan a partir del tablero (GitHub Projects → *Insights*) y del historial de issues y pull requests.

| Métrica | Cómo se mide | Resultado |
|---|---|---|
| **Velocity** | Puntos completados por sprint (campo *Estimación*) | Planeado: Sprint 1 = 30, Sprint 2 = 36, Sprint 3 = 38 (total 104). Entregados: 30, 36 y 38 puntos (**104 de 104**). Sin fechas de sprint no se calcula la velocidad por tiempo. |
| **Burndown** | Puntos restantes frente al tiempo del sprint | Proyecto 3: ver [las métricas con fechas de sprint](#proyecto-3-métricas-con-las-fechas-de-los-sprints). |
| **Lead time** | Tiempo desde *Backlog* hasta *Done* | Proyecto 3: ver [las métricas con fechas de sprint](#proyecto-3-métricas-con-las-fechas-de-los-sprints). |
| **Cycle time** | Tiempo desde *In Progress* hasta *Done* | Proyecto 3: ver [las métricas con fechas de sprint](#proyecto-3-métricas-con-las-fechas-de-los-sprints). |
| **Throughput** | Historias completadas por periodo | Proyecto 3: ver [las métricas con fechas de sprint](#proyecto-3-métricas-con-las-fechas-de-los-sprints). |

### Proyecto 3: métricas con las fechas de los sprints

Los sprints del Proyecto 3 tienen fechas reales: **Sprint 4** del 23 al 24 de noviembre, **Sprint 5** del 25 al 26 y **Sprint 6** el 27 de noviembre (día de la entrega). Las cifras salen del tablero con un script que se puede volver a correr cuando se quiera:

```bash
python scripts/metricas.py        # necesita la CLI gh con sesión iniciada
```

_Calculado el 24/11/2026 14:05 desde el tablero._

| Sprint | Fechas | Historias (hechas/total) | Puntos planeados | Puntos terminados | Velocidad (pts/día) |
|---|---|---|---|---|---|
| Sprint 1 | sin fechas (Proyecto 2) | 9/9 | 30 | 30 | — |
| Sprint 2 | sin fechas (Proyecto 2) | 11/11 | 36 | 36 | — |
| Sprint 3 | sin fechas (Proyecto 2) | 8/8 | 38 | 38 | — |
| Sprint 4 | 23/11 al 24/11 | 6/12 | 47 | 27 | 13,5 |
| Sprint 5 | 25/11 al 26/11 | 2/13 | 65 | 11 | 5,5 |
| Sprint 6 | 27/11 | 1/11 | 29 | 3 | 3,0 |

- **Historias del Proyecto 3 cerradas:** 9 de 36
- **Lead time** (Backlog → Done): promedio 19,8 h · mediana 19,6 h · máximo 20,2 h (n = 9)
- **Cycle time** (primer commit → Done): promedio 0,9 h · mediana 0,9 h · máximo 0,9 h (n = 3)
- **Throughput** (historias cerradas por día): 2026-11-24: 9

**Cómo leerlas**

- **Velocidad:** puntos de las historias cerradas dividido entre los días del sprint. Los sprints 1 a 3 son del Proyecto 2 y nunca tuvieron fechas, por eso no se les calcula velocidad por tiempo.
- **Lead time:** desde que la historia entra al tablero (se creó en *Backlog* el 23/11 a las 21:07) hasta que se cierra. Incluye el tiempo de espera en el backlog, por eso es mucho mayor que el cycle time.
- **Cycle time:** desde el primer commit que menciona la historia hasta que se cierra. Solo cuenta las historias con commits identificados por su número (`HU-xx`); las que se hicieron sin mencionarlo en el commit no entran.
- **Burndown:** los puntos restantes del Proyecto 3 son los planeados menos los terminados de cada sprint; al ser sprints de uno o dos días, se lee mejor con la tabla de velocidad que con una curva.
- El tablero no guarda la fecha en que una tarjeta pasa a *In Progress*, por eso el cycle time se aproxima con el primer commit.
- Las cifras de la tabla son un corte; se recalculan al cierre de cada sprint y antes de la entrega.

### Resumen del proyecto

- **Historias completadas:** 28 / 28 (fusionadas en `main`)
- **Velocity promedio:** 34,7 puntos por sprint (104 puntos entre 3 sprints)
- **Bugs encontrados:** 13 (documentados como issues cerrados, BUG-01 a BUG-13)
- **Tiempo promedio de resolución:** ver las métricas del Proyecto 3 (lead time y cycle time)

> Los sprints 1 a 3 (Proyecto 2) no tienen fechas; los del Proyecto 3 sí, y sus métricas están arriba. Los 13 bugs iniciales se crearon y cerraron al documentar el trabajo previo, por lo que no representan tiempos reales de resolución.

---

## Instalación y Uso

Pensado para Windows, que es donde se desarrolló. Al final hay los equivalentes para Linux y macOS.

#### 1. Requisitos

| Programa | Versión | Para qué | Cómo comprobar |
|---|---|---|---|
| Python | 3.12 o superior | Backend | `python --version` |
| Node.js | 20 o superior (con npm) | Compilar el frontend | `node --version` |
| PostgreSQL | probado con la 18 | Base de datos | `psql --version` |

#### 2. Descargar el proyecto

```bash
git clone https://github.com/SGil14/Cumulonimbus.git
cd Cumulonimbus
```

#### 3. Crear la base de datos (una sola vez)

Abre `psql` (o pgAdmin) como el usuario administrador de PostgreSQL y ejecuta, cambiando la contraseña:

```sql
CREATE ROLE lluvia_app LOGIN PASSWORD 'pon-aqui-una-contraseña-segura';
CREATE DATABASE lluvia_bogota OWNER lluvia_app;
```

No hay que crear las tablas a mano: las crean las migraciones en el paso 7.

#### 4. Configurar el `.env`

En la carpeta raíz del proyecto copia el archivo de ejemplo y edítalo:

```bash
copy .env.example .env        # en Linux/macOS: cp .env.example .env
```

Lo único obligatorio es `DATABASE_URL`, con la contraseña del paso anterior:

```ini
DATABASE_URL=postgresql+psycopg://lluvia_app:pon-aqui-una-contraseña-segura@localhost:5432/lluvia_bogota
```

> Si tu contraseña tiene caracteres especiales (`@`, `:`, `/`, `#`), escríbelos codificados en la URL (por ejemplo `@` → `%40`). El archivo `.env` está en `.gitignore`: **nunca lo subas al repositorio**.

El resto de variables tiene valores por defecto razonables; están explicadas en la [Configuración](#configuración-env).

#### 5. Instalar el backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

#### 6. Compilar el frontend

```bash
cd ..\frontend
npm install
npm run build
```

Esto genera `frontend/dist`, que el backend sirve solo. (Si usas el acceso directo del paso 7, este paso lo hace por ti la primera vez.)

#### 7. Arrancar

**Forma fácil (Windows):** doble clic en **`Abrir Cumulonimbus.bat`**. Compila el frontend si falta, abre el navegador en http://localhost:8000 y levanta el backend (aplicando antes las migraciones de la base de datos).

**Forma manual:**

```bash
cd backend
iniciar.bat
```

`iniciar.bat` ejecuta `alembic upgrade head` (crea o actualiza las tablas) y luego `uvicorn app.main:app --reload --port 8000`.

#### 8. Comprobar que todo funciona

| Qué abrir | Qué deberías ver |
|---|---|
| http://localhost:8000 | La app con el mapa de Bogotá. |
| http://localhost:8000/api/health | `{"estado":"ok","base_datos":"ok"}`: la app y la base están bien. |
| http://localhost:8000/docs | La documentación interactiva de la API. |

![Documentación interactiva de la API](docs/img/13-api-docs.png)

#### 9. Modo desarrollo del frontend (opcional)

Si vas a modificar el diseño, usa el servidor de desarrollo, que recarga en vivo:

```bash
cd frontend
npm run dev                  # http://localhost:5173
```

Reenvía las llamadas `/api` al backend en el puerto 8000. Si tu backend corre en otro puerto, define antes la variable `API_URL` (por ejemplo `set API_URL=http://localhost:8001`).

#### 10. Linux y macOS

`iniciar.bat` y el acceso directo son solo para Windows. Los equivalentes:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --port 8000
```

(Y `npm install && npm run build` en `frontend/`.) Estos pasos no se han probado en Linux ni en macOS.

#### 11. Con Docker (alternativa)

Si prefieres no instalar Python, Node ni PostgreSQL, el proyecto trae un `Dockerfile` y un `docker-compose.yml` que levantan la app y su base de datos juntas. Solo necesitas [Docker](https://www.docker.com/products/docker-desktop/) instalado.

1. En el archivo `.env` de la raíz agrega una contraseña para la base (solo letras y números):

   ```ini
   POSTGRES_PASSWORD=unaClaveSegura123
   ```

2. Construye y arranca todo:

   ```bash
   docker compose up --build
   ```

3. Abre http://localhost:8000.

Qué hace por ti:

- Compila el frontend y lo mete en la misma imagen que el backend (build en dos etapas).
- Crea un contenedor de PostgreSQL con su volumen `datos_postgres`: el histórico sobrevive a reinicios y a `docker compose down`. Para borrarlo también: `docker compose down -v`.
- Al arrancar, la app aplica las migraciones (`alembic upgrade head`) y espera a que la base esté lista.
- La base de datos no se publica fuera de Docker; solo se expone el puerto 8000 de la app.
- La imagen no lleva tu `.env` ni la carpeta de respaldo (ver `.dockerignore`) y no corre como administrador.

> **Estado:** la imagen se construyó y se probó con `docker compose` al preparar el despliegue (la hizo @jhonAleVelasco, sin correcciones) y es la que corre en Azure. El `docker-compose.yml` usa PostgreSQL 17; en Azure se usa PostgreSQL 16 gestionado y el desarrollo local se hizo con la 18.

### Cómo usar la app

#### La pantalla

| Zona | Qué hay |
|---|---|
| **Barra superior** | Nombre; botones **Radar**, **Historial**, **Diseño**, **Actualizar** y el interruptor de tema claro/oscuro. |
| **Panel** | Resumen del momento, buscador de destinos con ejemplos, formulario de ruta y lista de localidades con lo llovido hoy. |
| **Mapa** | Localidades coloreadas por lo acumulado hoy, estaciones, zonas de lluvia, ruta y radar. |

#### Guía rápida

1. **Mira el resumen.** El número grande es cuántas de las 71 estaciones registran lluvia ahora.
2. **Busca tu destino.** Escribe en «¿A dónde vas?» y pulsa Enter. También puedes tocar uno de los ejemplos.
3. **Lee la respuesta.** «No llueve cerca» o «Sí, llueve cerca», más las estaciones próximas.
4. **Pulsa «Ver cuándo ha llovido aquí»** para ver qué pasó en las últimas horas en ese punto.
5. **Si vas a moverte,** abre «Revisa la ruta», escribe origen y destino, elige el modo y pulsa «Ver lluvia en el trayecto».
6. **Pulsa «Actualizar»** para traer datos frescos (la app no se refresca sola).
7. **Enciende el «Radar»** si quieres ver de dónde viene la lluvia (recuerda: es lluvia en el aire).
8. **Cambia el «Diseño»** y el tema al que más te guste.

#### Colores del mapa

- **Relleno de cada localidad:** cuánto ha llovido hoy, con la escala del SAB: hasta 10 mm (bajo), hasta 30 (moderado), hasta 50 (alto), más de 50 (muy alto).
- **Punto de cada estación:** seco, o el color de su intensidad actual si llueve (tabla de [Ver dónde llueve ahora](#ver-dónde-llueve-ahora)).

### Configuración (`.env`)

Se lee del archivo `.env` de la carpeta raíz o de variables de entorno (las variables de entorno tienen prioridad, que es lo que se usa en la nube).

| Variable | Por defecto | Qué hace |
|---|---|---|
| `DATABASE_URL` | **obligatoria** | Conexión a PostgreSQL con el driver `psycopg` (`postgresql+psycopg://usuario:clave@host:5432/base`). |
| `CACHE_ESTACIONES_SEGUNDOS` | `90` | Segundos que se reutilizan los datos del SAB antes de volver a consultarlo. |
| `MINUTOS_LECTURA_VIEJA` | `30` | Una lectura más vieja que esto se marca como desactualizada y no cuenta como lluvia. |
| `ESTACIONES_CERCANAS` | `3` | Cuántas estaciones cercanas se muestran al consultar un destino. |
| `RECOLECTOR_ACTIVO` | `true` | Enciende o apaga el recolector del histórico. |
| `RECOLECTOR_INTERVALO_MINUTOS` | `5` | Cada cuántos minutos el recolector guarda lecturas. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Orígenes permitidos para el frontend en desarrollo (formato JSON). No hace falta en producción, porque el backend sirve el frontend. |
| `LOG_LEVEL` | `INFO` | Nivel de los registros. |
| `JWT_SECRET_KEY` | vacío | **Secreto.** Llave con la que se firman los tokens de inicio de sesión (mínimo 16 caracteres). Sin ella, registro e inicio de sesión responden `503`. Ver [Autenticación y roles](#autenticación-y-roles). |
| `JWT_EXPIRA_MINUTOS` | `60` | Minutos que dura un token. |
| `ADMIN_CORREO` | vacío | Quien se registre con este correo queda como administrador. |
| `GRAFANA_URL` | vacío | Opcional. Si se define, el panel del administrador muestra un enlace a Grafana. |
| `IDECA_API_KEY` | vacío | Opcional. Activa el geocodificador oficial de IDECA (ver [geocodificación](#geocodificación-de-destinos)). |
| `RUTA_URL` | `https://valhalla1.openstreetmap.de/route` | Servicio de rutas. Cámbialo solo si montas tu propia instancia de Valhalla. |
| `SAB_URL`, `IDECA_URL`, `NOMINATIM_USER_AGENT` | ver `backend/app/config.py` | Direcciones y cabeceras de los servicios externos. |

---

## Documentación de la API

El backend expone una API JSON; el frontend es solo uno de sus clientes. Toda la documentación interactiva, con la posibilidad de probar cada endpoint, está en **`/docs`**.

| Endpoint | Descripción |
|---|---|
| `GET /api/health` | Estado de la app y de la base de datos. |
| `GET /api/estaciones` | Las 71 estaciones con su estado actual. |
| `GET /api/resumen` | Dónde llueve ahora y acumulado por localidad. |
| `GET /api/cercanas?lat=&lon=` | Estaciones más cercanas a un punto. |
| `GET /api/destino?q=` | Resuelve un destino (localidad, coordenadas, barrio, lugar, dirección o esquina) y devuelve ubicación, barrio y lluvia cercana. |
| `GET /api/ruta?origen=&destino=&modo=` | Trayecto de un lugar a otro (`auto`, `bus`, `bicicleta`, `a_pie`) y en qué tramos llueve ahora. |
| `GET /api/historial/serie?periodo=&localidad=` | Cuánto llovió en cada intervalo (por hora en `6h` y `24h`, por día en `7d` y `30d`). |
| `GET /api/historial/ranking?periodo=` | Localidades ordenadas por lo que llovió en el periodo. |
| `GET /api/historial/destino?lat=&lon=&periodo=` | Cuándo llovió cerca de un punto (las 3 estaciones más cercanas). |
| `GET /api/atajo?q=` | Una frase en texto plano que dice si llueve en un destino; pensada para el atajo de iPhone. |
| `GET /api/atajo/ruta?origen=&destino=&modo=` | Una **tarjeta HTML** con mapa que dice si llueve en una ruta (con `lat=` y `lon=` en lugar de `origen=` usa la ubicación del teléfono; con `formato=texto` devuelve texto con emojis). |
| `POST /api/auth/registro`, `POST /api/auth/login`, `GET /api/auth/yo` | Cuenta de usuario: registro, inicio de sesión (token JWT) y quién soy. Ver [Autenticación y roles](#autenticación-y-roles). |
| `GET/POST /api/favoritos`, `PUT/DELETE /api/favoritos/{id}` | Destinos favoritos del usuario. **Exigen token.** |
| `GET /api/admin/usuarios`, `GET /api/admin/usuarios/{id}/favoritos`, `PUT /api/admin/usuarios/{id}/rol`, `DELETE /api/admin/usuarios/{id}`, `GET /api/admin/estado` | Administración de usuarios, roles y estado del sistema. **Solo administradores.** |
| `GET /api/prediccion?lat=&lon=` | Probabilidad de lluvia en la próxima hora cerca de un punto, con el método usado (`modelo` o `persistencia`). Ver [Inteligencia artificial](#inteligencia-artificial). |
| `GET /api/radar` | Imagen del radar (PNG transparente en base64) y la zona que cubre. |
| `GET /api/localidades` | Contorno de las localidades (GeoJSON), usado para dibujar el mapa. |

Los endpoints de lluvia son públicos; solo los de favoritos y administración piden `Authorization: Bearer <token>`.

Con `?actualizar=true`, `/api/estaciones` y `/api/resumen` ignoran la caché y consultan al SAB en ese instante.

**Ejemplos:**

```bash
# ¿Dónde llueve ahora?
curl http://localhost:8000/api/resumen

# ¿Llueve cerca de una esquina?
curl "http://localhost:8000/api/destino?q=Calle%2072%20con%20Carrera%2010"

# Historial de las últimas 24 horas en Chapinero
curl "http://localhost:8000/api/historial/serie?periodo=24h&localidad=Chapinero"

# Ruta en bicicleta
curl "http://localhost:8000/api/ruta?origen=Portal%2080&destino=Chapinero&modo=bicicleta"
```

**Códigos de error útiles:** `502` si el SAB no responde; `503` si un servicio de geocodificación o de rutas falla por red (conviene reintentar: la app **no** responde «no existe» cuando en realidad fue un fallo de red).

---

## Autenticación y roles

Proyecto 3. Consultar la lluvia sigue siendo **público**: no hace falta cuenta para ver el mapa, buscar un destino, ver el historial ni usar el atajo de iPhone. La cuenta sirve para guardar **destinos favoritos**, y su rol decide qué más se puede hacer.

### Cómo funciona

```mermaid
sequenceDiagram
    participant U as Usuario
    participant API as API (FastAPI)
    participant BD as PostgreSQL
    U->>API: POST /api/auth/registro {correo, clave}
    API->>BD: guarda el usuario con la clave en hash (scrypt)
    API-->>U: 201 {id, correo, rol}
    U->>API: POST /api/auth/login {correo, clave}
    API->>BD: busca el usuario y compara el hash
    API-->>U: 200 {access_token (JWT), expira_en_segundos}
    U->>API: GET /api/favoritos  + Authorization: Bearer <token>
    API->>API: verifica firma, vencimiento y usuario
    API-->>U: 200 solo los favoritos de ese usuario
    U->>API: GET /api/favoritos  (sin token o con token vencido)
    API-->>U: 401
```

- **Contraseñas:** se guardan con hash **scrypt** y una sal distinta por usuario. Nunca se guardan ni se devuelven en texto plano. Mínimo 8 caracteres, con al menos una letra y un número.
- **Token:** un **JWT** firmado con HS256 que lleva el usuario (`sub`), el correo, el **rol** y la expiración (`exp`). Dura 60 minutos (`JWT_EXPIRA_MINUTOS`).
- **Mensajes de error:** un correo que no existe y una contraseña equivocada responden lo mismo (`401`), para no revelar qué correos están registrados.
- **Correos:** se guardan en minúsculas; no se permiten repetidos (`409`).

### Roles

| Rol | Cómo se obtiene | Qué puede hacer |
|---|---|---|
| *(sin cuenta)* | — | Todo lo de lluvia: estaciones, resumen, destino, ruta, historial, radar, atajo. |
| `usuario` | Es el rol por omisión al registrarse. | Lo anterior, más **crear, editar, ver y borrar sus propios favoritos**. No puede ver ni tocar los de otros (responde `404`). |
| `administrador` | Registrarse con el correo configurado en `ADMIN_CORREO`, o que otro administrador lo cambie. | Lo anterior, más **listar los usuarios** (con sus favoritos), **cambiar el rol** de cualquiera, **eliminar cuentas** y ver el **estado del sistema**. No puede quitarse el rol si es el único administrador ni eliminar su propia cuenta. |

### Endpoints

| Endpoint | Quién | Descripción |
|---|---|---|
| `POST /api/auth/registro` | Público | Crea la cuenta. `201`; `409` si el correo ya existe; `422` si los datos no son válidos. |
| `POST /api/auth/login` | Público | Devuelve el token. `401` si las credenciales no coinciden. |
| `GET /api/auth/yo` | Con token | El usuario del token. |
| `GET /api/favoritos` | Con token | Mis favoritos. |
| `POST /api/favoritos` | Con token | Guarda un favorito `{nombre, texto}` (máximo 50 por usuario; el nombre no se repite). |
| `PUT /api/favoritos/{id}` | Con token | Edita uno de mis favoritos. |
| `DELETE /api/favoritos/{id}` | Con token | Borra uno de mis favoritos (`204`). |
| `GET /api/admin/usuarios` | Administrador | Lista los usuarios con cuántos favoritos tiene cada uno. `403` si eres `usuario`. |
| `GET /api/admin/usuarios/{id}/favoritos` | Administrador | Los favoritos de ese usuario. |
| `PUT /api/admin/usuarios/{id}/rol` | Administrador | Cambia el rol `{"rol": "usuario" \| "administrador"}`. `409` si eres el único administrador y te lo quitas. |
| `DELETE /api/admin/usuarios/{id}` | Administrador | Elimina la cuenta y sus favoritos (`204`). `409` si intentas borrarte a ti mismo. |
| `GET /api/admin/estado` | Administrador | Resumen: usuarios, favoritos, estaciones, lecturas, última lectura, estado de la IA y enlace a Grafana. |

### Probarlo con `curl`

```bash
# 1. Registrarse
curl -X POST http://localhost:8000/api/auth/registro \
  -H "Content-Type: application/json" \
  -d '{"correo":"ana@ejemplo.com","clave":"Clave1234"}'

# 2. Iniciar sesión y guardar el token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"correo":"ana@ejemplo.com","clave":"Clave1234"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. Usar el token en un endpoint protegido
curl http://localhost:8000/api/auth/yo -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/favoritos -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"nombre":"Casa","texto":"Portal 80"}'

# 4. Lo mismo sin token: 401
curl -i http://localhost:8000/api/favoritos

# 5. Con rol insuficiente: 403
curl -i http://localhost:8000/api/admin/usuarios -H "Authorization: Bearer $TOKEN"
```

En Windows PowerShell, usa `curl.exe` (no el alias `curl`) y escribe el JSON entre comillas simples; o prueba todo desde `/docs`, con el botón **Authorize**.

### Configurar la llave de firma

La llave con la que se firman los tokens es un **secreto**: no está en el código ni en el repositorio. Se pasa por variable de entorno (mínimo 16 caracteres; usa una larga y aleatoria):

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

| Dónde corre | Cómo se configura |
|---|---|
| Local | `JWT_SECRET_KEY=...` en el `.env` (ver `.env.example`). |
| Docker Compose | `JWT_SECRET_KEY` en el `.env` de la raíz; `docker-compose.yml` se la pasa a la app. |
| Kubernetes | Clave `JWT_SECRET_KEY` del Secret `cumulonimbus-secretos` (ver `k8s/secret.example.yaml`). `scripts/k8s-desplegar.ps1` la genera sola la primera vez y se la agrega a un Secret que ya existía sin ella. |

Sin llave, el registro y el inicio de sesión responden `503` y el resto de la app sigue funcionando. Si la llave cambia, las sesiones abiertas dejan de valer y los usuarios deben iniciar sesión de nuevo. Con `ADMIN_CORREO=tu-correo@ejemplo.com`, quien se registre con ese correo queda como administrador.

### En la interfaz

El botón **Entrar** de la barra abre la ventana de la cuenta (registro e inicio de sesión). Con la sesión iniciada, el buscador ofrece **☆ Guardar «…» en mis favoritos** y muestra la lista **Mis favoritos** (un clic busca ese destino; la × lo quita). La sesión se conserva al recargar la página; un token vencido la cierra solo. Los administradores ven además, en la misma ventana, el **estado del sistema** (usuarios, lecturas, última lectura del recolector, IA y enlace a Grafana) y la lista de usuarios, desde la cual pueden **cambiar el rol**, **ver los favoritos** y **eliminar** cuentas (con confirmación; no pueden cambiarse ni borrarse a sí mismos).

### Límites conocidos

- Los tokens no se pueden revocar antes de que venzan (no hay lista de bloqueo ni renovación); «Cerrar sesión» solo borra el token del navegador.
- No hay recuperación de contraseña ni verificación del correo.
- No hay límite de intentos de inicio de sesión.

---

## Atajo para iPhone

Con la app **Atajos** del iPhone se puede preguntar «¿llueve?» sin abrir el navegador: se escribe un lugar o una ruta y el teléfono contesta en una ventana. Son **tres atajos** que se arman a mano y llaman a estos endpoints del servidor:

| Endpoint | Para qué | Qué responde |
|---|---|---|
| `GET /api/atajo?q=` | ¿Llueve cerca de un lugar? | Una frase en texto plano |
| `GET /api/atajo/ruta?origen=&destino=&modo=` | ¿Me mojo en esta ruta? | Una **tarjeta HTML** con mapa (o texto con `formato=texto`) |

### Qué responde

**Atajo de lugar** (`/api/atajo`): acepta lo mismo que `/api/destino` (localidad, barrio, lugar, dirección, esquina o coordenadas `lat,lon`).

| Situación | Respuesta |
|---|---|
| No llueve | `No llueve cerca de Quinta Camacho, Chapinero. Ninguna estación cercana registra lluvia ahora.` |
| No llueve, pero llovió hoy | `No llueve cerca de Quinta Camacho, Chapinero. Hoy cayeron 7,4 mm en la estación más cercana.` |
| Llueve | `Sí, llueve cerca de Quinta Camacho, Chapinero. Colegio Simón Rodríguez, a 1,8 km, marca lluvia fuerte (13,2 mm/h).` |
| Lecturas viejas | `No se puede asegurar para Quinta Camacho, Chapinero: las estaciones más cercanas no tienen lectura reciente.` |
| Destino no encontrado | `No encontré «xyz». Prueba con otra dirección o con un barrio.` |

**Atajo de ruta** (`/api/atajo/ruta`): una tarjeta con un banner de color (verde «Ruta sin lluvia», azul «Hay lluvia en tu ruta» o gris «No se puede asegurar»), un **mapa de calles con el recorrido pintado por tramos** (verde seco, azul lluvia, gris sin datos), las estaciones cercanas, el tiempo, la distancia, la hora aproximada de llegada y la lista de tramos.

Parámetros: `destino` (obligatorio); `origen` **o** `lat` y `lon` (ubicación del teléfono, con coma o con punto decimal); `modo` (`Carro / moto`, `Bus`, `Bici`, `A pie`, o `auto`, `bus`, `bicicleta`, `a_pie`); `formato` (`html` por defecto o `texto`).

<img src="docs/img/atajo-07-ruta-tarjeta.png" alt="Tarjeta de la ruta con el mapa" width="300">

### Cómo se ve al usarlo

| Atajo de lugar | | Atajo de ruta | | |
|---|---|---|---|---|
| <img src="docs/img/atajo-02-lugar-entrada.png" width="230"> | <img src="docs/img/atajo-03-lugar-resultado.png" width="230"> | <img src="docs/img/atajo-04-ruta-origen.png" width="230"> | <img src="docs/img/atajo-05-ruta-destino.png" width="230"> | <img src="docs/img/atajo-06-ruta-modo.png" width="230"> |
| Se escribe el lugar | La respuesta | Se escribe el origen | Se escribe el destino | Se elige el modo |

### Cómo armar los atajos

**1. Atajo de lugar**

<img src="docs/img/atajo-08-lugar-armado.png" alt="Atajo de lugar armado" width="300">

1. **Solicitar entrada** (tipo *Texto*) con la pregunta «¿A dónde vas?».
2. **Reemplazar texto**: espacio → `%20`.
3. **Reemplazar texto**: `#` → `%23` (sobre el *Texto actualizado* anterior).
4. **Obtener contenido de URL**: `http://TU-IP:8000/api/atajo?q=` seguido de la variable *Texto actualizado*.
5. **Mostrar resultado** del contenido de la URL.

**2. Atajo de ruta**

<img src="docs/img/atajo-09-ruta-armado-1.png" width="260"> <img src="docs/img/atajo-10-ruta-armado-2.png" width="260"> <img src="docs/img/atajo-11-ruta-armado-3.png" width="260">

1. **Solicitar entrada** «Origen» → los dos **Reemplazar texto** (espacio y `#`) → **Establecer variable** `Origen`.
2. **Solicitar entrada** «Destino» → los dos **Reemplazar texto** → **Establecer variable** `Destino`.
3. Una acción **Lista** con `Carro / moto`, `Bus`, `Bici` y `A pie` → **Elegir de la lista** → **Reemplazar texto** (espacio → `%20`) → **Establecer variable** `Modo`.
4. **URL**: `http://TU-IP:8000/api/atajo/ruta?origen=` **[Origen]** `&destino=` **[Destino]** `&modo=` **[Modo]**.
5. **Mostrar vista web** con esa URL: abre la tarjeta en una ventana **dentro de Atajos**, sin pasar a Safari.

**Variante: usar tu ubicación como origen** (en el atajo de ruta, en lugar de escribir el origen)

1. Quita los pasos del «Origen» y agrega **Obtener ubicación actual** (la primera vez, iOS pide permiso de ubicación para Atajos).
2. **Obtener detalles de ubicaciones** → *Latitud* → **Establecer variable** `Lat`; y otra igual con *Longitud* → `Lon`.
3. La **URL** pasa a ser: `http://TU-IP:8000/api/atajo/ruta?lat=` **[Lat]** `&lon=` **[Lon]** `&destino=` **[Destino]** `&modo=` **[Modo]**.

El iPhone entrega los decimales con coma (`4,6097`); el servidor acepta coma o punto. La tarjeta muestra «Tu ubicación (barrio, localidad)» como origen.

**3. Atajo maestro**

<img src="docs/img/atajo-12-maestro-armado.png" alt="Atajo maestro armado" width="260"> <img src="docs/img/atajo-01-menu-maestro.png" alt="Menú del atajo maestro" width="300">

Un **Seleccionar del menú** («¿Qué quieres consultar?») con dos opciones, «Un lugar» y «Una ruta». Debajo de cada una, **Ejecutar atajo** con el atajo de lugar y con el de ruta. Solo el maestro se añade a la pantalla de inicio.

### Detalles que importan

- **Espacios y `#`:** Atajos **no codifica** el texto que se pega en una URL. Un espacio corta la dirección («Movistar Arena» llegaba como «Movistar») y un `#` descarta todo lo que sigue, y casi todas las direcciones de Bogotá lo llevan. Por eso los dos *Reemplazar texto*.
- **Variables:** se eligen de la lista (burbujas de color), sin espacios alrededor, y los nombres de los parámetros van en minúscula (`origen`, `destino`, `modo`).
- **Mostrar vista web** (ruta) y **Mostrar resultado** (lugar): son las acciones que pintan la respuesta al lanzar el atajo desde la pantalla de inicio. «Detener y mostrar resultado» deja la ventana vacía.
- **`TU-IP`:** es la IP del computador que corre el servidor; `iniciar.bat` la muestra al arrancar y **cambia** al cambiar de red. El iPhone y el computador deben estar en la misma red. Con la app en Azure se usa la dirección pública `https://…` y sin puerto.
- **Mapa de la tarjeta:** las calles son teselas de OpenStreetMap, así que el teléfono necesita internet. Si no cargan, el recorrido se dibuja igual.

### Estado

- **Probado en un iPhone** contra el servidor local, en la misma red Wi-Fi (capturas de arriba): atajo de lugar, de ruta con mapa y maestro.
- **Con la app desplegada:** el atajo funciona igual contra su URL pública (`https://…`, sin puerto), siempre que la versión publicada incluya estos endpoints.
- **«Mi ubicación» como origen:** el servidor acepta `lat` y `lon` con coma o punto decimal (probado con `lat=4,6097&lon=-74,0817`: devuelve «Tu ubicación (El Liston, Los Mártires) → Portal 80»). Los pasos para armar la variante en Atajos están arriba; **falta probarla en un iPhone y agregar las capturas**.

---

## Base de datos

Seis tablas, creadas por las migraciones de Alembic (`backend/alembic/versions/`).

| Tabla | Para qué sirve | Campos principales |
|---|---|---|
| `estaciones` | Catálogo de pluviómetros. | `id_sensor` (clave), `nombre`, `localidad`, `latitud`, `longitud`, `tecnologia` |
| `lecturas` | **Histórico**: una fila por estación y hora de lectura. Es la tabla para análisis. | `id_sensor`, `fecha_lectura`, `valor_5min`, `acumulado_dia`; única por (`id_sensor`, `fecha_lectura`) |
| `geocache` | Destinos ya resueltos, para no volver a preguntar a internet. | `consulta_normalizada`, `latitud`, `longitud`, `barrio`, `localidad`, `proveedor`, `aproximada`, `usos` |
| `consultas` | Registro de cada búsqueda de destino. | `texto`, `tipo`, `encontrado`, `barrio`, `localidad`, `proveedor`, `lloviendo_cerca` |
| `usuarios` | Cuentas registradas. | `correo` (único), `clave_hash` (scrypt), `rol` (`usuario` o `administrador`) |
| `favoritos` | Destinos guardados por cada usuario. | `usuario_id`, `nombre` (único por usuario), `texto` |

Ejemplo de análisis directamente en SQL: las horas más lluviosas del último mes.

```sql
SELECT date_trunc('hour', fecha_lectura) AS hora, SUM(valor_5min) AS mm
FROM lecturas
WHERE fecha_lectura > now() - interval '30 days'
GROUP BY 1 ORDER BY mm DESC LIMIT 10;
```

---

## Reglas y cálculos

### Intensidad actual

El SAB entrega los milímetros caídos en los últimos 5 minutos. La app los multiplica por 12 para tener **mm por hora** y clasifica:

| mm/h | Intensidad |
|---|---|
| 0 | Sin lluvia |
| menos de 2,5 | Ligera |
| de 2,5 a menos de 7,6 | Moderada |
| de 7,6 a menos de 50 | Fuerte |
| 50 o más | Muy fuerte |

### Acumulado del día (escala del SAB)

Bajo: hasta 10 mm · Moderado: hasta 30 · Alto: hasta 50 · Muy alto: más de 50.

### Lectura desactualizada

Si la última lectura de una estación tiene más de **30 minutos**, se marca como desactualizada y **no cuenta como lluvia activa** (una estación sin reportar no debe aparecer como «lloviendo» con un dato viejo).

### Cálculo del historial

- **Por hora:** diferencia entre lecturas del `acumulado_dia` (que el SAB reinicia a medianoche). No importa si las lecturas llegan cada 2 o cada 5 minutos.
- **Por día:** el máximo `acumulado_dia` de cada estación ese día.
- Para una localidad o para Bogotá se **promedian** las estaciones.
- Un intervalo sin lecturas es **«sin datos»**, distinto de «seco». La pantalla muestra el porcentaje de datos disponibles y desde cuándo hay registros.
- El total de cada **día** incluye la lluvia caída antes del primer registro; el total por **hora** solo cuenta desde que hay lecturas guardadas. Por eso, si el histórico empezó a media mañana, los totales de hora y de día pueden diferir.

### Geocodificación de destinos

`/api/destino?q=...` resuelve el texto en este orden:

1. **Localidad** («Chapinero»): usa las estaciones de esa localidad, sin salir a internet.
2. **Coordenadas** («4.6486, -74.0628»).
3. **Barrio, lugar, dirección o esquina**, con estos proveedores en orden:
   1. **Caché** en PostgreSQL (`geocache`).
   2. **IDECA**, solo si hay `IDECA_API_KEY` (opcional).
   3. **Catastro de Bogotá (placas domiciliarias)**: gratis y sin clave. Entiende la nomenclatura bogotana: `Carrera 7 # 55-25`, `Calle 63 Sur # 80-15`, `Carrera 90 bis # 130-44` y esquinas como `Calle 72 con Carrera 10` o `Av Boyacá con Calle 80` (reconoce Boyacá, Caracas, NQS, Autopista Norte, Séptima, Ciudad de Cali y El Dorado). Si el número exacto no existe, usa la placa más cercana de la misma cuadra y marca el resultado como **aproximado**.
   4. **Nominatim** (OpenStreetMap): lugares, parques, centros comerciales y barrios («Portal 80», «Galerías»).

El barrio y la localidad salen de las capas públicas del Catastro (sector catastral y localidad). Cada búsqueda queda en `consultas` y cada destino resuelto en `geocache`.

**IDECA (opcional):** el geocodificador oficial exige una clave gratuita que entrega IDECA (https://mapas.bogota.gov.co/api/). Usa los mismos datos de placas que el proveedor de Catastro, así que hoy no es necesaria; si la consigues, ponla en `IDECA_API_KEY` y se activa sola, sin tocar código.

### Cálculo de la ruta

1. Pide el trayecto a **Valhalla** (servicio gratuito de OpenStreetMap) y decodifica la polilínea.
2. Parte el camino en puntos cada **400 m**.
3. Para cada punto toma la **estación más cercana** y decide: **lluvia** (llueve en esa estación), **seco**, o **sin datos** (estación a más de 4 km o con lectura vieja).
4. Agrupa los puntos consecutivos en tramos y escribe el resumen.

### Radar

El backend descarga el KMZ público de reflectividad, extrae la imagen y la zona geográfica que cubre, y la entrega en `/api/radar` (con 2 minutos de caché). Si el radar falla, la app sigue funcionando sin él. El filtrado de ecos débiles se hace en el navegador, por color (`frontend/src/lib/radarFiltrado.ts`).

---

## Los cinco diseños

La experiencia es la misma; cambia el estilo. Se elige con el botón **«Diseño»**.

| Diseño | Idea |
|---|---|
| **Clima** (por defecto) | App del tiempo amigable: cielo claro o noche azul, tarjetas redondeadas. |
| **Tablero** | Grafito y verde limón, tipografía condensada, bloques sólidos. |
| **Radar** | Consola meteorológica: panel lateral denso, datos en monoespaciada, anillos de alcance centrados en el radar. |
| **Minimalista** | Casi sin adornos: el mapa, una frase y una barra de búsqueda; las localidades se despliegan con «Ver localidades». |
| **Mapa vivo** | El mapa lo es todo: el cielo cambia según llueva o no y cae **lluvia animada** sobre las zonas con lluvia. Respeta la opción «reducir movimiento» del sistema. |

**Clima, tema oscuro**

![Diseño Clima, tema oscuro](docs/img/02-diseno-clima-oscuro.png)

**Tablero**

![Diseño Tablero](docs/img/03-diseno-tablero.png)

**Radar**

![Diseño Radar](docs/img/04-diseno-radar.png)

**Minimalista**

![Diseño Minimalista](docs/img/05-diseno-minimalista.png)

**Mapa vivo**

![Diseño Mapa vivo](docs/img/06-diseno-mapa-vivo.png)

### Cómo agregar un diseño nuevo

Cada diseño es un archivo CSS autocontenido en `frontend/src/disenos/` más su paleta del mapa. Para crear uno:

1. Crea `frontend/src/disenos/mi-diseno.css` (puedes partir de `clima.css`).
2. Regístralo en la lista `DISENOS` de `frontend/src/disenos/index.ts`, con su paleta del mapa para tema claro y oscuro.
3. Define las variables `--h-*` que usan las piezas compartidas (historial, gráfico y ruta, en `comun.css`).

---

## Estructura del proyecto

```
Cumulonimbus/
├── backend/
│   ├── app/
│   │   ├── main.py                # Arranque de FastAPI; sirve también el frontend compilado
│   │   ├── config.py              # Configuración (.env)
│   │   ├── api/routes/            # Endpoints: lluvia, destino, atajo (+ atajo_ruta y atajo_mapa), mapa, radar, historial, ruta, health,
│   │   │                          #            auth, favoritos y admin
│   │   ├── api/deps.py            # Quién hace la petición (token) y qué rol tiene
│   │   ├── services/              # Lógica: cliente SAB, reglas de lluvia, geocodificación,
│   │   │                          #         historial, ruta, radar, barrios
│   │   ├── repositories/          # Lectura y escritura en PostgreSQL
│   │   ├── db/                    # Conexión y tablas
│   │   ├── jobs/recolector.py     # Guarda el histórico cada 5 minutos
│   │   ├── models/                # Modelos de datos (pydantic)
│   │   └── core/                  # Caché, zona horaria y seguridad (hash de claves y JWT)
│   ├── alembic/                   # Migraciones de la base de datos
│   ├── tests/                     # Pruebas automáticas
│   ├── iniciar.bat                # Migra y levanta la API (Windows)
│   └── requirements.txt
├── frontend/                      # React + Vite + TypeScript + MapLibre
│   └── src/
│       ├── components/            # Mapa, panel, buscador, historial, ruta, radar…
│       ├── hooks/                 # Datos, tema, diseño, historial, sesión
│       ├── lib/                   # API, formatos, geometría, lluvia animada, filtro del radar
│       └── disenos/               # Un CSS por diseño + paletas del mapa
├── ml/                            # Inteligencia artificial: datos, entrenamiento, evaluación y pruebas
├── monitoreo/                     # Prometheus y Grafana para docker compose (dashboard en JSON)
├── k8s/                           # Manifiestos de Kubernetes
├── scripts/                       # Despliegue en AKS y tráfico de prueba
├── docs/ia.md                     # La funcionalidad de IA: decisión, datos, modelo, evaluación y límites
├── docs/img/                      # Capturas de este README
├── Dockerfile                     # Imagen única: backend + frontend compilado
├── docker-compose.yml             # La app, su PostgreSQL, Prometheus y Grafana
├── .dockerignore
├── Abrir Cumulonimbus.bat            # Un clic: compila el frontend si falta y abre la app
├── .env.example                   # Plantilla de configuración
└── README.md
```

El backend sigue capas: **rutas** (HTTP) → **servicios** (reglas de negocio, funciones puras donde se puede) → **repositorios** (base de datos). Así la lógica se prueba sin base de datos.

---

## Pruebas

```bash
cd backend
.venv\Scripts\python -m pytest
```

Hay **110 pruebas** del backend que cubren las reglas de intensidad y acumulado, la lectura de direcciones del Catastro, la geocodificación, el historial, la ruta, el radar, la predicción de lluvia, la coherencia del dashboard de Grafana con las métricas de la API y la **autenticación** (registro, inicio de sesión, token ausente, inválido y vencido, rol insuficiente, favoritos ajenos, panel de administración; estas usan SQLite en memoria y no necesitan PostgreSQL). La carpeta `ml/` tiene otras **29** (`cd ml && python -m pytest`): preparación de datos, entrenamiento, simulador y una prueba de que la API calcula las variables igual que el entrenamiento. Usan datos de ejemplo guardados en `backend/tests/fixtures`.


---

## Despliegue en Azure

La aplicación está **desplegada en Microsoft Azure Kubernetes Service (AKS)**. El despliegue lo hizo y lo documentó @jhonAleVelasco.

| Dato | Valor |
|---|---|
| **App en vivo** | http://cumulonimbus-bogota.centralus.cloudapp.azure.com |
| **Grafana** | http://cumulonimbus-grafana.centralus.cloudapp.azure.com:3000 (usuario `admin`) |
| **Servicio** | Azure Kubernetes Service (plan gratuito), región Central US |
| **Suscripción** | Azure for Students del equipo |
| **Grupo de recursos** | `rg-cumulonimbus-k8s` |
| **Versión actual** | Imagen `acrcumulonimbusk8se1d4.azurecr.io/cumulonimbus:sha-<commit>` |
| **Detalle técnico** | Sección [Kubernetes y monitoreo](#kubernetes-y-monitoreo) y guion en [`docs/demo-kubernetes.md`](docs/demo-kubernetes.md) |

> El clúster se **apaga cuando no se usa** para no gastar el crédito de estudiante. Si los links no responden, está apagado: se prende con `az aks start -g rg-cumulonimbus-k8s -n aks-cumulonimbus` (unos 5 minutos).

### Qué hay en Azure

| Recurso | Qué es | Para qué sirve |
|---|---|---|
| `rg-cumulonimbus-k8s` | Grupo de recursos | Agrupa todo el despliegue, con etiquetas `proyecto=cumulonimbus` |
| `aks-cumulonimbus` | Clúster AKS | 1 nodo `Standard_D2s_v3` (2 vCPU, 8 GiB) donde corren la app, PostgreSQL, Prometheus y Grafana |
| `acrcumulonimbusk8se1d4` | Azure Container Registry | Guarda las imágenes con versión; el clúster las descarga **sin contraseña** (identidad administrada, rol AcrPull) |
| Service `api` | LoadBalancer con IP pública | Publica la app con el nombre `cumulonimbus-bogota.centralus.cloudapp.azure.com` |
| Service `grafana` | LoadBalancer con IP pública | Publica Grafana con el nombre `cumulonimbus-grafana.centralus.cloudapp.azure.com` |

Los nombres DNS los pone Azure a partir de la anotación `service.beta.kubernetes.io/azure-dns-label-name` de cada Service (`k8s/30-api.yaml` y `k8s/monitoreo/20-grafana.yaml`), así que no cambian aunque cambie la IP.

### Prender, actualizar y apagar

```powershell
# Prender el clúster y conectar kubectl
az aks start -g rg-cumulonimbus-k8s -n aks-cumulonimbus
az aks get-credentials -g rg-cumulonimbus-k8s -n aks-cumulonimbus --overwrite-existing

# Desplegar la versión actual de main (construye, sube al ACR y actualiza todo)
powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1 -Acr acrcumulonimbusk8se1d4 -SinMetricsServer -Region centralus

# Ver lo que corre
kubectl get pods,svc -n cumulonimbus

# Apagar al terminar
az aks stop -g rg-cumulonimbus-k8s -n aks-cumulonimbus
```

Para crear todo desde cero en otra suscripción: `scripts/aks-crear.ps1 -Suscripcion "<id>"`.

### Costos aproximados

Encendido, el nodo `Standard_D2s_v3` cuesta unos 2–3 USD al día; el plan gratuito de AKS no cobra el plano de control. Apagado solo se pagan el ACR Basic (~5 USD al mes) y las IP públicas reservadas (céntimos). Borrar todo: `az group delete -n rg-cumulonimbus-k8s --yes`.

### Versión 1 (Proyecto 2): Azure Container Apps, retirada

En octubre de 2026 la app se desplegó en **Azure Container Apps** (grupo `rg-cumulonimbus`, con PostgreSQL gestionado, Key Vault e identidad administrada). Esa suscripción se quedó sin crédito, así que **ese despliegue ya no está en línea** y su histórico no se migró. La documentación completa, con capturas del portal y los scripts, está en [`docs/despliegue/`](docs/despliegue/README.md).


---

## Kubernetes y monitoreo

Proyecto 3. La app corre en un clúster de **Kubernetes** con **Prometheus** y **Grafana** dentro del mismo clúster. Funciona igual en el Kubernetes de **Docker Desktop** (clúster local, sin costo) y en **AKS** (Azure), que es donde está publicada: ver [Despliegue en Azure](#despliegue-en-azure).

### Qué se despliega

```mermaid
flowchart LR
    U["Navegador<br/>http://localhost"] --> SVC["Service api<br/>(LoadBalancer :80)"]
    subgraph NS1["namespace cumulonimbus"]
        SVC --> A1["Pod api #1"]
        SVC --> A2["Pod api #2"]
        HPA["HPA<br/>2 a 6 réplicas por CPU"] -.-> A1
        REC["Pod recolector<br/>(1 réplica)"]
        JOB["Job migraciones<br/>alembic upgrade head"]
        PG[("StatefulSet postgres<br/>+ volumen 2 Gi")]
        A1 --> PG
        A2 --> PG
        REC --> PG
        JOB --> PG
    end
    subgraph NS2["namespace monitoreo"]
        PROM["Prometheus :9090"] -->|/metrics cada 10 s| A1
        PROM --> A2
        PROM --> REC
        GRAF["Grafana :3000<br/>dashboard Cumulonimbus"] --> PROM
    end
```

| Archivo | Qué crea |
|---|---|
| `k8s/00-namespace.yaml` | Namespace `cumulonimbus` |
| `k8s/01-configmap.yaml` | **ConfigMap** con la configuración no sensible (recolector apagado en la API) |
| `k8s/secret.example.yaml` | Ejemplo del **Secret** (`DATABASE_URL`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, admin de Grafana). El real nunca se sube (`k8s/secret.yaml` está en `.gitignore`) |
| `k8s/10-postgres.yaml` | PostgreSQL 17 como **StatefulSet** con volumen persistente y Service headless |
| `k8s/20-migraciones-job.yaml` | **Job** que aplica las migraciones una sola vez por despliegue |
| `k8s/30-api.yaml` | **Deployment de la API con 2 réplicas**, probes de *readiness* (`/api/health/ready`) y *liveness* (`/api/health/live`), `requests`/`limits`, y **Service** LoadBalancer |
| `k8s/31-recolector.yaml` | El recolector en su propio Deployment de **1 réplica**, para no consultar el SAB varias veces |
| `k8s/40-hpa.yaml` | **HorizontalPodAutoscaler**: de 2 a 6 réplicas cuando la CPU pasa del 50 % |
| `k8s/extras/metrics-server.yaml` | metrics-server oficial (lo necesita el HPA), con `--kubelet-insecure-tls` solo para Docker Desktop |
| `k8s/monitoreo/10-prometheus.yaml` | Prometheus con permisos (RBAC) para descubrir los pods anotados con `prometheus.io/scrape: "true"` |
| `k8s/monitoreo/20-grafana.yaml` | Grafana con la fuente de datos y el dashboard ya cargados |

### Métricas de la API (`/metrics`)

| Métrica | Tipo | Qué mide |
|---|---|---|
| `cumulonimbus_http_requests_total{metodo,ruta,estado}` | Counter | Peticiones atendidas (throughput) |
| `cumulonimbus_http_request_duration_seconds` | Histogram | Latencia de la API |
| `cumulonimbus_http_requests_in_progress` | Gauge | Peticiones en curso por réplica |
| `cumulonimbus_estaciones_lloviendo` | Gauge | Estaciones del SAB que registran lluvia |
| `cumulonimbus_estaciones_total` | Gauge | Estaciones recibidas en la última consulta |
| `cumulonimbus_sab_consultas_total{resultado}` | Counter | Consultas al SAB (ok o error) |
| `cumulonimbus_sab_duracion_seconds` | Histogram | Tiempo de respuesta del SAB |
| `cumulonimbus_ia_predicciones_total{metodo}` | Counter | Predicciones entregadas (`modelo` o `persistencia`) |
| `cumulonimbus_ia_prediccion_duracion_seconds` | Histogram | Latencia de la predicción |
| `cumulonimbus_ia_probabilidad_ultima` | Gauge | Probabilidad de la última predicción del modelo |

La etiqueta `ruta` usa la plantilla de la ruta (`/api/historial/serie`), no la URL completa, para no crear una serie por cada búsqueda. `/metrics` y los sondeos de salud no se cuentan.

**Dashboard de Grafana** (11 paneles): throughput por ruta, latencia p50 y p95, estaciones con lluvia, réplicas arriba, peticiones en curso por réplica, % de errores 5xx, tiempo de respuesta del SAB y, para la IA, predicciones por minuto y método, latencia de la predicción, predicciones de la última hora y probabilidad de la última predicción. Su JSON está en `monitoreo/grafana/dashboards/cumulonimbus.json` y es el mismo que carga el clúster (una prueba lo verifica).

### Monitoreo con Docker Compose (sin clúster)

`docker compose up --build` levanta la API, PostgreSQL, **Prometheus** y **Grafana**, con todo ya configurado:

1. En el `.env` define `POSTGRES_PASSWORD` y `GRAFANA_PASSWORD`.
2. `docker compose up --build`
3. La app: <http://localhost:8000> · Grafana: <http://localhost:3000> (usuario `admin`) · Prometheus: <http://localhost:9090>
4. Para ver moverse las gráficas: `python scripts/trafico.py --url http://localhost:8000 --segundos 120 --usuarios 20`

Prometheus lee `http://app:8000/metrics` cada 10 segundos (`monitoreo/prometheus.yml`) y Grafana carga la fuente de datos y el dashboard sin pasos manuales (`monitoreo/grafana/provisioning/`).

### Desplegar

Requisitos: Docker Desktop con **Kubernetes activado** (Settings → Kubernetes → Enable) y `kubectl` apuntando a `docker-desktop`.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1
```

El script construye la imagen, crea los Secrets con contraseñas aleatorias (solo la primera vez), levanta PostgreSQL, corre las migraciones, despliega la API, el recolector, el HPA, metrics-server, Prometheus y Grafana, y al final muestra `kubectl get pods,svc`. Se puede correr las veces que sea.

| Qué | Dónde |
|---|---|
| App | http://localhost |
| Métricas | http://localhost/metrics |
| Prometheus | `kubectl port-forward svc/prometheus 9090:9090 -n monitoreo` y luego http://localhost:9090 (solo es accesible dentro del clúster) |
| Grafana | http://localhost:3000 (usuario `admin`) |

Contraseña de Grafana:

```powershell
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((kubectl get secret grafana-admin -n monitoreo -o jsonpath='{.data.admin-password}')))
```

### Generar tráfico y ver el autoescalado

```powershell
python scripts/trafico.py --segundos 150 --usuarios 60
kubectl get hpa -n cumulonimbus -w
```

El script solo usa la librería estándar de Python y mezcla los endpoints más usados (más algunos 404). En la prueba, con 60 usuarios la CPU llegó al 65 % y el HPA subió la API **de 2 a 3 réplicas** en menos de un minuto, sin errores; al terminar el tráfico vuelve a 2.

### Comandos útiles

```powershell
kubectl get pods,svc -n cumulonimbus          # lo que pide la sustentación
kubectl get pods,svc -n monitoreo
kubectl top pods -n cumulonimbus              # CPU y memoria por pod
kubectl logs deploy/recolector -n cumulonimbus --tail 20
kubectl delete namespace cumulonimbus monitoreo   # borrar todo
```

### Decisiones

- **Recolector separado**: la API tiene varias réplicas; si cada una recolectara, el SAB recibiría varias consultas cada 5 minutos. Va en su propio Deployment de 1 réplica con estrategia `Recreate`.
- **Migraciones en un Job**: así las réplicas no corren `alembic upgrade` al mismo tiempo.
- **Liveness sin base de datos**: si PostgreSQL se cae, Kubernetes no reinicia las réplicas sin necesidad; la *readiness* sí la revisa y las saca del balanceo.
- **PostgreSQL dentro del clúster**: StatefulSet con volumen, para que el entorno sea autocontenido y gratis. En la nube se puede cambiar por el PostgreSQL gestionado de Azure cambiando solo `DATABASE_URL` en el Secret.
- **Prometheus y Grafana con manifiestos propios**: todo queda versionado y comentado en `k8s/monitoreo/`, sin depender de Helm.

### Imagen versionada y pipeline (GitHub Actions)

`.github/workflows/ci-cd.yml`:

| Cuándo | Qué hace |
|---|---|
| Pull Request hacia `main` | Corre las 80 pruebas del backend y construye la imagen (backend + frontend) sin publicarla |
| Fusión a `main` | Además **publica la imagen en GitHub Container Registry**: `ghcr.io/sgil14/cloud_cumulonimbus:sha-<commit>` y `:latest` |
| Etiqueta `vX.Y.Z` | Publica también `:vX.Y.Z` |
| Fusión a `main` con AKS configurado | Copia la imagen al ACR y actualiza la API y el recolector del clúster |

No usa contraseñas guardadas para publicar: el `GITHUB_TOKEN` de Actions basta. El script de despliegue también etiqueta cada imagen con el commit (`cumulonimbus:sha-<commit>`), así cada despliegue tiene versión y se puede volver atrás.

Para que el pipeline despliegue en AKS hay que configurar en el repositorio (*Settings → Secrets and variables → Actions*):
- Variables: `AKS_NOMBRE`, `AKS_GRUPO`, `ACR_NOMBRE`.
- Secreto: `AZURE_CREDENTIALS`, el JSON de una entidad de servicio con rol *Colaborador* sobre el grupo del clúster (`az ad sp create-for-rbac --role contributor --scopes <id-del-grupo> --json-auth`).

Sin esas variables, el pipeline solo prueba, construye y publica.

### En Azure (AKS)

Los mismos manifiestos sirven en AKS. El clúster se crea en la suscripción del equipo con:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\aks-crear.ps1 -Suscripcion "<id o nombre de la suscripción>"
powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1 -Acr <nombre-del-acr> -SinMetricsServer -Region centralus
```

`aks-crear.ps1` crea el grupo `rg-cumulonimbus-k8s`, un **ACR** y un **AKS** (plan gratuito, 1 nodo `Standard_D2s_v3`: 2 vCPU y 8 GiB), y conecta el ACR al clúster con identidad administrada, **sin usuario ni contraseña**. Después `k8s-desplegar.ps1 -Acr` construye la imagen, la sube al ACR con su versión y despliega todo. AKS ya trae metrics-server. Las IP públicas salen en `kubectl get svc`.

Para no gastar crédito: `az aks stop -g rg-cumulonimbus-k8s -n aks-cumulonimbus` (y `az aks start` antes de la demo).

Probado en la suscripción *Azure for Students* del equipo (24/11/2026): la app quedó en una IP pública del Service `api`, Grafana en la del Service `grafana` (puerto 3000), y la imagen sale del ACR con versión (`acrcumulonimbusk8se1d4.azurecr.io/cumulonimbus:sha-...`). Con `scripts/trafico.py --usuarios 80` el HPA subió la API de 2 a 6 réplicas y atendió 15.214 peticiones sin errores.

Límites de *Azure for Students* que obligaron a ajustar el despliegue:

| Límite | Efecto | Solución |
|---|---|---|
| Solo algunos tamaños de máquina, y varios con cuota 0 (Bs, Dalsv7) | El nodo nunca se creaba y AKS quedaba en «Creating» | `Standard_D2s_v3` (familia DSv3, con cuota) |
| Máximo 3 IP públicas | AKS usa una para su salida, la API otra y Grafana otra | Prometheus es `ClusterIP`: Grafana lo consulta por dentro y se ve con `kubectl port-forward` |

### Demo

El guion paso a paso de la sustentación está en [`docs/demo-kubernetes.md`](docs/demo-kubernetes.md).

---

## Inteligencia artificial

**Qué hace:** estima la probabilidad de que llueva en la **próxima hora** cerca de un destino. Aparece en el resultado de una búsqueda, bajo «Próxima hora», y está en `GET /api/prediccion?lat=&lon=`.

**Cómo:** una regresión logística (scikit-learn, comparada con un árbol de gradiente) entrenada con lecturas reales de las 71 estaciones del SAB. Usa la lluvia de la estación en los últimos 10, 30 y 60 minutos, la de sus 3 estaciones vecinas, el acumulado del día y la hora. El modelo se publica como un JSON de unos números (`backend/app/ia/modelo.json`), así que la API lo evalúa sin instalar scikit-learn.

**Respaldo:** si no hay modelo, no hay una hora de lecturas continuas guardadas cerca o la base de datos falla, la API responde con la regla «si llueve ahora, seguirá lloviendo» y dice por qué. El campo `metodo` siempre indica cuál se usó.

**Honestidad sobre los resultados:** con los datos disponibles (solo dos eventos de lluvia, del 14 y del 17 de octubre de 2026) el modelo **todavía no supera** a esa regla simple en la prueba (F1 0,17 frente a 0,38). La interfaz lo avisa («estimación experimental»). El detalle, el diagnóstico y lo que haría falta para mejorarlo están en [`docs/ia.md`](docs/ia.md).

```bash
cd ml
pip install -r requirements.txt
python preparar_datos.py --lecturas ../dataset/lecturas.csv --estaciones ../dataset/estaciones.csv --corte 2026-10-17
python entrenar.py --todo     # evalúa y publica ml/modelo/modelo.json
# copiar modelo.json y metricas.json a backend/app/ia/
```

`ml/simulador.py` genera lluvia **sintética** solo para probar y demostrar; sus datos y modelos están marcados y nunca se usan para evaluar.

---

## Construir, desplegar y correr todo el stack

Guía de punta a punta del Proyecto 3: de la imagen al clúster, con monitoreo y la funcionalidad de IA. Los detalles de cada pieza están en las secciones enlazadas.

```mermaid
flowchart LR
    COD["Código<br/>backend + frontend"] -->|docker build| IMG["Imagen<br/>cumulonimbus:sha-…"]
    IMG -->|push| REG["Registro<br/>GHCR o ACR"]
    REG --> K8S["Clúster<br/>Docker Desktop o AKS"]
    K8S --> API["API + recolector<br/>+ PostgreSQL"]
    API -->|/metrics| PROM["Prometheus"] --> GRAF["Grafana"]
    ML["ml/<br/>datos y modelo"] -.->|IA| API
```

### 1. Construir la imagen

Una sola imagen contiene el backend y el frontend compilado (el `Dockerfile` usa dos etapas). Desde la raíz:

```bash
docker build -t cumulonimbus:local .
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET_KEY=... cumulonimbus:local
```

Para probar con una base de datos ya lista, `docker compose up --build` levanta la app y PostgreSQL juntos (ver [Instalación y Uso](#instalación-y-uso); define `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` en el `.env`).

### 2. Publicar la imagen

| Registro | Cómo |
|---|---|
| **GitHub Container Registry** | Automático: cada fusión a `main` publica `ghcr.io/sgil14/cloud_cumulonimbus:sha-<commit>` y `:latest` ([pipeline](#imagen-versionada-y-pipeline-github-actions)). |
| **Azure Container Registry (ACR)** | `k8s-desplegar.ps1 -Acr <nombre>` construye la imagen, la etiqueta con el commit y la sube. A mano: `az acr login --name <acr>`, `docker tag cumulonimbus:local <acr>.azurecr.io/cumulonimbus:v1`, `docker push <acr>.azurecr.io/cumulonimbus:v1`. |

Cada despliegue usa una etiqueta con versión, nunca solo `latest`, para poder volver atrás.

### 3. Desplegar en el clúster

```powershell
# Clúster local (Docker Desktop con Kubernetes activado)
powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1

# AKS en Azure (crea antes el clúster con scripts/aks-crear.ps1)
powershell -ExecutionPolicy Bypass -File .\scripts\k8s-desplegar.ps1 -Acr <nombre-del-acr> -SinMetricsServer -Region centralus
```

El script aplica los manifiestos de [`k8s/`](k8s/) en este orden: namespaces y ConfigMap → **Secrets** (contraseña de PostgreSQL, `DATABASE_URL`, **llave JWT** y admin de Grafana, generados al azar la primera vez) → PostgreSQL → Job de **migraciones** → API (2 réplicas) y recolector → HPA → Prometheus y Grafana. Se puede correr las veces que haga falta. Para comprobar:

```powershell
kubectl get pods,svc -n cumulonimbus
kubectl get pods,svc -n monitoreo
```

Detalle de cada manifiesto, decisiones y límites de Azure for Students: [Kubernetes y monitoreo](#kubernetes-y-monitoreo).

### 4. Levantar el stack de monitoreo

Prometheus y Grafana se despliegan con el mismo script (namespace `monitoreo`). Para verlos:

| Qué | Cómo |
|---|---|
| Métricas crudas de la API | `http://<IP de la app>/metrics` |
| Prometheus | `kubectl port-forward svc/prometheus 9090:9090 -n monitoreo` → http://localhost:9090 |
| **Grafana y su dashboard** | `http://<IP de Grafana>:3000` (usuario `admin`; contraseña en el Secret `grafana-admin`, ver el comando en [Kubernetes y monitoreo](#kubernetes-y-monitoreo)) |

El dashboard «Cumulonimbus» (7 paneles) y la fuente de datos de Prometheus vienen ya cargados desde [`k8s/monitoreo/20-grafana.yaml`](k8s/monitoreo/20-grafana.yaml). Para ver las gráficas moverse, genera carga con `python scripts/trafico.py --segundos 150 --usuarios 60`.

### 5. La funcionalidad de IA

La predicción de lluvia a corto plazo se documenta en [`docs/ia.md`](docs/ia.md): decisión, datos, modelo y evaluación frente a la línea base. El código está en [`ml/`](ml/):

```bash
cd ml
pip install -r requirements.txt
python preparar_datos.py     # arma entrenamiento.csv y prueba.csv desde la tabla `lecturas`
python entrenar.py           # entrena, evalúa y guarda el modelo
```

### 6. Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Manifiestos de Kubernetes | [`k8s/`](k8s/) |
| Secret de ejemplo (sin valores reales) | [`k8s/secret.example.yaml`](k8s/secret.example.yaml) |
| Dashboards de Grafana | [`k8s/monitoreo/20-grafana.yaml`](k8s/monitoreo/20-grafana.yaml) |
| Scripts de despliegue y de carga | [`scripts/`](scripts/) |
| Pipeline de CI/CD | [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) |
| IA: decisión, datos y modelo | [`docs/ia.md`](docs/ia.md) y [`ml/`](ml/) |
| Guion de la demo de Kubernetes | [`docs/demo-kubernetes.md`](docs/demo-kubernetes.md) |
| Guion de la demo del contexto y la autenticación | [`docs/demo-autenticacion.md`](docs/demo-autenticacion.md) |
| Autenticación y roles | [Autenticación y roles](#autenticación-y-roles) |

---

## Límites que debes conocer

Para no engañarte con lo que muestra la app:

- **Un pluviómetro mide un punto.** Si llueve a 3 km de la estación más cercana, esa estación puede marcar 0. Una llovizna muy fina puede no registrarse: estos pluviómetros cuentan cuando se acumula una cantidad mínima de agua.
- **Las lecturas llegan cada ~2 minutos** y la app solo consulta cuando abres o actualizas; una lluvia que acaba de empezar puede tardar unos minutos en aparecer.
- **El radar ve lluvia en el aire.** Puede mostrar lluvia que no llega al suelo, y sus colores no están calibrados contra los pluviómetros: la equivalencia entre color e intensidad es orientativa.
- **Las zonas de color son una estimación visual** alrededor de cada estación; no hay medición entre estaciones.
- **La ruta usa la lluvia de ahora,** no un pronóstico de lo que pasará cuando llegues.
- **No es un pronóstico.** Cumulonimbus dice lo que está pasando y lo que pasó, no lo que va a pasar.
- **El histórico empieza cuando el servidor se enciende por primera vez.** No hay datos anteriores.

---

## Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| `Abrir Cumulonimbus.bat` abre una página que no carga | El servidor tarda unos segundos en arrancar: recarga la página. Si sigue, mira la ventana negra por errores. |
| Error de conexión a la base (`password authentication failed`, `connection refused`) | PostgreSQL apagado, o el `DATABASE_URL` del `.env` no coincide con tu usuario, contraseña, puerto o nombre de base. |
| `/api/health` dice que la base falla | Igual que el anterior; verifica que `psql` entra con esos mismos datos. |
| Veo una versión vieja de la app | Hay un servidor antiguo ocupando el puerto 8000. Cierra su ventana, abre `Abrir Cumulonimbus.bat` y recarga con **Ctrl+F5**. |
| El historial dice «Aún hay pocos datos» | Es normal al empezar: el histórico solo se llena mientras el servidor está encendido. |
| La app no registra la lluvia que estoy viendo | Mira [Límites que debes conocer](#límites-que-debes-conocer): la estación más cercana puede estar lejos o no haber registrado todavía una llovizna fina. Prueba con «Actualizar» y el radar. |
| Error 502 «El SAB no está respondiendo» | El servicio del SAB está caído o lento. Intenta de nuevo en unos minutos. |
| Error 503 al buscar una dirección o calcular una ruta | Falló un servicio externo (Catastro, Nominatim, Valhalla), por ejemplo por la red de tu empresa o colegio. Reintenta. |
| El radar no aparece | Está apagado por defecto: pulsa «Radar». Si no hay ecos moderados o fuertes, no se dibuja nada (es lo esperado). |
| El atajo dice «falta `destino`» o encuentra otro lugar (por ejemplo «Movistar» en vez de «Movistar Arena») | Un espacio o un `#` **corta la dirección web**. Hay que usar los dos «Reemplazar texto» del atajo: espacio → `%20` y `#` → `%23`. En el servidor se ve exactamente qué llegó (`GET /api/atajo?...`). |
| El atajo no conecta con el servidor | El iPhone y el computador deben estar en la misma red, el servidor encendido y la IP vigente: cambia al cambiar de red y la muestra `iniciar.bat` al arrancar. |
| Al lanzar el atajo desde la pantalla de inicio sale una ventana vacía | Usa **Mostrar resultado** (lugar) o **Mostrar vista web** (ruta); «Detener y mostrar resultado» no se pinta fuera del editor. |
| La tarjeta de la ruta sale sin calles | El teléfono necesita internet para las teselas de OpenStreetMap; el recorrido se dibuja igual. |
| GitHub marca conflicto al fusionar un archivo que es igual en las dos ramas | Suele ser la diferencia de saltos de línea (LF/CRLF). Se elige la versión de `main`. Para evitarlo, un archivo compartido lo sube solo su dueño. |
| `npm run build` falla | Comprueba que Node sea de la versión 20 o superior y borra `frontend/node_modules` para repetir `npm install`. |

---

## Mejoras futuras

| Estado | Función |
|---|---|
| ✅ | Backend: cliente SAB, reglas, API, PostgreSQL y recolector |
| ✅ | Geocodificación de direcciones, esquinas, barrios y lugares |
| ✅ | Frontend con cinco diseños, tema claro/oscuro y versión para celular |
| ✅ | Historial por horas y por días |
| ✅ | Ruta de un lugar a otro |
| ✅ | Radar con filtro de ecos débiles y zonas de color por estación |
| ✅ | Docker (imagen construida y probada) |
| ✅ | Despliegue en Azure Container Apps (Proyecto 2, retirado) |
| ✅ | Despliegue en Azure Kubernetes Service (AKS) con Prometheus, Grafana y autoescalado |
| ✅ | Atajo para iPhone: lugar, ruta con mapa y atajo maestro |
| ✅ | Radar funcionando en Azure (el 502 era de Container Apps) |
| ⏳ | «Mi ubicación» como origen en el atajo de ruta (servidor y pasos listos; falta probarlo en el iPhone) |
| ✅ | GitHub Actions: integración continua, publicación de la imagen y despliegue en AKS |
| ⏳ | `.gitattributes` para unificar los saltos de línea del repositorio |

---

## Fuentes de datos y créditos

Todos son servicios públicos y gratuitos:

| Dato | Fuente |
|---|---|
| Pluviómetros | SAB / IDIGER: https://app.sab.gov.co/sab/lluvias.htm |
| Radar meteorológico | Radar del IDIGER (reflectividad, KMZ público) |
| Direcciones, barrios y localidades | Catastro Bogotá (placas domiciliarias, sector catastral, localidad) |
| Lugares y barrios | Nominatim, de OpenStreetMap (© colaboradores de OpenStreetMap) |
| Rutas | Valhalla, de OpenStreetMap |
| Mapa de la tarjeta del atajo | Teselas de OpenStreetMap (© colaboradores de OpenStreetMap) |

Este proyecto no está afiliado al IDIGER, a la Alcaldía de Bogotá ni a OpenStreetMap. Los datos pertenecen a sus respectivas entidades.

Aún no se ha definido una licencia para el código.

---

## Enlaces importantes

- **Aplicación desplegada (AKS):** http://cumulonimbus-bogota.centralus.cloudapp.azure.com
- **Grafana:** http://cumulonimbus-grafana.centralus.cloudapp.azure.com:3000
- **Repositorio del curso:** [SGil14/cloud_Cumulonimbus](https://github.com/SGil14/cloud_Cumulonimbus)
- **GitHub Project (tablero Kanban):** [Cumulonimbus · Tablero Kanban](https://github.com/users/SGil14/projects/2)
- **Repositorio previo de la aplicación base:** [SGil14/Cumulonimbus](https://github.com/SGil14/Cumulonimbus)
