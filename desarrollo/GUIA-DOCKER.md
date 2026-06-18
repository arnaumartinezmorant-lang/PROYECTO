# Guia paso a paso: levantar y demostrar TODO el proyecto con Docker

Esta guia monta el proyecto completo en **una sola maquina con varios contenedores
Docker** (lo que recomendo el profesor) y demuestra su funcionamiento: balanceo,
comunicacion entre componentes, alta disponibilidad (failover), copias de seguridad,
monitorizacion e informes. Todos los comandos son copiar y pegar.

## Que se monta y a que rol corporativo (Linux) equivale

| Contenedor | Rol en el contenedor | Equivalente en el diseno (Ubuntu Server) |
|------------|----------------------|-------------------------------------------|
| `lb`     | Balanceador / proxy inverso (nginx) | LB01 / HAProxy en Ubuntu Server |
| `web01`  | Servidor web + aplicacion           | WEB01 con Nginx |
| `web02`  | Servidor web + aplicacion (replica) | WEB02 con Nginx |
| volumen `dbdata` | Base de datos compartida    | SQL01 + endpoint HAProxy (PostgreSQL + Patroni) |
| `monitor`| Metricas y disponibilidad           | Prometheus + Grafana |

Los contenedores se comunican por una **red interna de Docker** llamada `backend`
(equivale a la VLAN del diseno). Se hablan por su nombre: `web01`, `web02`, `lb`.

## Tiempo estimado para montarlo todo

| Tarea | Tiempo |
|-------|--------|
| Instalar Docker Desktop (solo la primera vez) | 10-20 min |
| Descargar/clonar el proyecto | 1-2 min |
| `docker compose up -d --build` (1a vez: descarga imagenes + build) | 3-8 min |
| Recorrer toda la demostracion (pasos 2-7) | 10-15 min |
| **Total con Docker ya instalado** | **~15-25 min** |
| **Total desde cero (instalando Docker)** | **~30-45 min** |

> A partir de la segunda vez, `docker compose up -d` arranca en **segundos** (las imagenes
> ya estan descargadas y construidas).

---

## 0. Requisitos (una sola vez)

1. Instalar **Docker Desktop** (Windows/Mac) o Docker Engine (Linux): https://docs.docker.com/get-docker/
2. Comprobar que funciona:
   ```bash
   docker --version
   docker compose version
   ```
3. Descargar el proyecto (si no lo tienes):
   ```bash
   git clone https://github.com/arnaumartinezmorant-lang/PROYECTO.git
   cd PROYECTO/desarrollo
   ```
   > Si ya lo tienes, solo entra en la carpeta `desarrollo`.

---

## 1. Construir y arrancar todo (un solo comando)

```bash
docker compose up -d --build
```

Esto construye la imagen de la aplicacion y levanta los 4 servicios. El balanceador
genera el certificado HTTPS automaticamente la primera vez. Comprueba que estan arriba:

```bash
docker compose ps
```
Debes ver `lb`, `web01`, `web02` y `monitor` en estado *Up/running*.

---

## 2. Demostrar que el servicio funciona y el BALANCEO

**Interfaz grafica:** abre el navegador en **https://localhost** (acepta el aviso del
certificado autofirmado). Veras la intranet con su interfaz: un **panel de metricas**
(KPIs, incidencias por estado y ranking de tecnicos), iniciar sesion, registrar
usuarios, listar/crear incidencias, cambiar su estado (si eres tecnico) y ver el
historial. Arriba a la derecha se muestra que **nodo (WEB01/WEB02)** te esta sirviendo,
asi que el balanceo se ve en vivo al recargar.

Usuarios de demostracion ya creados:
- Tecnico: `tecnico@corp.local` / `Tecnico123!`
- Administracion: `admin@corp.local` / `Admin123!`
- Oficina: `oficina@corp.local` / `Oficina123!`

Tambien por linea de comandos (API):
```bash
# Pagina principal (a traves del balanceador, por HTTPS)
curl -k https://localhost/

# Que nodo responde cada vez (debe alternar WEB01 / WEB02)
for i in 1 2 3 4 5 6; do curl -k -s https://localhost/whoami; echo; done
```
En Windows (PowerShell), si prefieres no usar curl:
```powershell
1..6 | % { (Invoke-WebRequest -Uri https://localhost/whoami -SkipCertificateCheck).Content }
```
**Que demuestra:** el balanceador reparte las peticiones entre los dos servidores web.

---

## 2b. (Opción) Balanceo con HAProxy y panel gráfico

Si quieres enseñar el balanceador **HAProxy** (el nombre que usa el diseño) con un
**cuadro de mando visual**, arranca el laboratorio con el override de HAProxy:
```bash
docker compose -f docker-compose.yml -f docker-compose.haproxy.yml up -d
```
- Balanceo: `curl http://localhost:8080/whoami` (repite; alterna WEB01/WEB02).
- **Panel gráfico de HAProxy:** abre `http://localhost:8404` en el navegador. Verás los dos
  servidores, su estado (UP/DOWN) y las sesiones que atiende cada uno.
- Failover en vivo: `docker compose stop web01` → en el panel WEB01 pasa a **DOWN** y todo el
  tráfico va a WEB02 sin corte. `docker compose start web01` → vuelve a **UP**.

> Nginx (servicio `lb`, en `https://localhost`) y HAProxy (`http://localhost:8080`) hacen lo
> mismo: balancear el frontal. Usa el que prefieras para la demo; HAProxy añade el panel visual.

## 3. Demostrar la COMUNICACION entre componentes

```bash
# El balanceador ve a los dos nodos por la red interna de Docker
docker compose exec lb ping -c 2 web01
docker compose exec lb ping -c 2 web02

# Los nodos web comparten la misma base de datos (volumen dbdata)
docker compose exec web01 ls -l /data/intranet.db
docker compose exec web02 ls -l /data/intranet.db
```
**Que demuestra:** los contenedores se comunican por nombre dentro de la red `backend`
y comparten el almacenamiento de datos (igual que WEB01/WEB02 hablan con el endpoint HAProxy).

---

## 4. Demostrar la ALTA DISPONIBILIDAD (failover) — lo mas importante

```bash
# 1) Estado normal: responden los dos
for i in 1 2 3 4; do curl -k -s https://localhost/whoami; echo; done

# 2) Apagamos WEB01 a proposito
docker compose stop web01

# 3) El servicio SIGUE funcionando: ahora responde solo WEB02
for i in 1 2 3 4; do curl -k -s https://localhost/whoami; echo; done

# 4) Recuperamos WEB01 y vuelve a repartirse la carga
docker compose start web01
sleep 5
for i in 1 2 3 4; do curl -k -s https://localhost/whoami; echo; done
```
**Que demuestra:** al caer un servidor, el balanceador deja de enviarle trafico y el
servicio continua sin corte (continuidad del negocio).

---

## 5. Ejecutar el PLAN DE PRUEBAS de caja negra (12 casos)

```bash
docker compose exec web01 python pruebas/run_tests.py
```
> Si el contenedor no tiene la carpeta `pruebas`, ejecutalo desde el host apuntando al
> balanceador:
> ```bash
> BASE_URL=https://localhost python3 pruebas/run_tests.py
> ```
**Que demuestra:** registro, login, validaciones, permisos por rol e historial (12/12).

---

## 6. COPIAS DE SEGURIDAD cifradas y RESTAURACION

```bash
# Copia 3-2-1 cifrada (AES-256) de la base de datos
docker compose exec web01 sh -c "apk add --no-cache sqlite gnupg >/dev/null 2>&1; bash scripts/backup.sh /data/intranet.db /data/backups"

# Restauracion (verifica integridad)
docker compose exec web01 sh -c "bash scripts/restore.sh \$(ls -1t /data/backups/local/*.enc | head -1) /tmp/restaurada.db"
```
> La imagen de la app es Debian slim; si `apk` no existe usa `apt-get install -y sqlite3 gnupg`.
> Alternativa sencilla y garantizada: ejecuta los scripts desde el host (ver apartado 8).

**Que demuestra:** se generan copias cifradas y se recuperan con `integrity_check = ok`.

---

## 7. MONITORIZACION e INFORMES

```bash
# Metricas y disponibilidad (el contenedor monitor ya esta midiendo)
docker compose logs monitor | tail -20

# Informe de negocio (incidencias por estado, tiempo medio, ranking de tecnicos)
docker compose exec web01 sh -c "apk add --no-cache sqlite >/dev/null 2>&1; sqlite3 /data/intranet.db < observabilidad/informes-sql.sql"
```
**Que demuestra:** disponibilidad del servicio y explotacion de la informacion.

---

## 8. Alternativa garantizada SIN depender de utilidades dentro del contenedor

Si algun comando dentro del contenedor falla, puedes reproducir TODO desde el host con
un solo script (solo necesita Python 3, no necesita Docker):

```bash
bash run-lab.sh
```
Genera todas las evidencias en `evidencias/` (balanceo, failover, backup/restore,
pruebas, monitor, informes). Es la via mas robusta para la demostracion.

---

## 9. Ver logs y parar

```bash
# Logs de cada servicio
docker compose logs lb
docker compose logs web01
docker compose logs web02

# Parar y limpiar todo (borra contenedores; conserva volumenes)
docker compose down

# Parar y borrar tambien los datos/volumenes (empezar de cero)
docker compose down -v
```

---

## 10. (Opcional, avanzado) Demostrar con un PostgreSQL real

El diseno corporativo usa PostgreSQL. Si quieres ensenar un PostgreSQL real
en contenedor, puedes anadir este servicio en una prueba aparte:

```yaml
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: "Cl4veFuerte!2025"
    ports: [ "5432:5432" ]
    volumes:
      - "./db/postgresql-setup.sql:/docker-entrypoint-initdb.d/10-setup.sql:ro"
    networks: [ backend ]
```
Al arrancar, PostgreSQL ejecuta solo el guion `db/postgresql-setup.sql` (roles con
minimo privilegio, pgcrypto y notas de Patroni + HAProxy). Para conectarte y comprobarlo:
```bash
docker compose exec db psql -U postgres -d intranet_corporativa -c "\du"   # lista roles
```
> Nota: para que la aplicacion use PostgreSQL en lugar de SQLite habria que cambiar la
> cadena de conexion y el driver (psycopg2); en el laboratorio se mantiene SQLite por
> simplicidad y reproducibilidad. Este paso solo demuestra que el PostgreSQL real arranca
> y acepta el esquema con sus roles.

---

## Checklist: qué pide el proyecto y dónde se cumple

| Lo que pide el profesor / proyecto | Dónde se cumple | Cómo demostrarlo |
|------------------------------------|-----------------|------------------|
| Coherencia de IPs, puertos, VLANs y servidores | Memoria apt. 11.5 + `red/plan-direccionamiento.md` + diagramas | Enseñar la tabla y los diagramas |
| Qué hace cada servidor (IP, servicios, comunicación) | Memoria 11.5 (inventario) + diagramas 10/11 | Tabla de servidores |
| Proyecto **funcional y demostrable** | Laboratorio Docker | Pasos 1-2 (`docker compose up`) |
| Balanceo de carga | `lb` (Nginx) / HAProxy | Pasos 2 y 2b |
| **Alta disponibilidad (failover)** | Nginx/HAProxy + 2 web | Paso 4 (+ panel HAProxy en 2b) |
| Interfaz y gestión de incidencias (RBAC) | App web | `https://localhost` (login, incidencias, panel) |
| Scripts (backup, restore, logs, disco, alta usuario) | `desarrollo/scripts/` | Pasos 6 y 7 |
| Cifrado (AES en copias; LUKS/pgcrypto en diseño) | `scripts/backup.sh`, `db/postgresql-setup.sql` | Paso 6 (la copia `.enc` no tiene texto en claro) |
| Base de datos + endpoint único (HAProxy/Listener) | SQLite (lab) / PostgreSQL (apt. 10) | Paso 10 (PostgreSQL real opcional) |
| Directorio y políticas por rol (FreeIPA/HBAC) | `scripts/new-empleado-ldap.sh` + diseño | Mostrar el script y el apt. 12 |
| **Plan de pruebas real con evidencias y métricas** | `pruebas/run_tests.py` + `evidencias/` | Paso 5 (12/12) + `EVIDENCIAS.md` |
| Monitorización / explotación de la información | `monitor/` + `observabilidad/informes-sql.sql` | Paso 7 + panel de métricas |
| Conclusiones propias | Memoria (apartado Conclusiones) | — |

> Consejo para la defensa: durante los pasos 2, 4 y 5 **haz capturas de pantalla** (interfaz,
> panel de HAProxy con WEB01 DOWN, salida de las 12 pruebas) y añádelas a la memoria como
> evidencias. La carpeta `evidencias/` ya trae salidas reales regenerables con `bash run-lab.sh`.

---

## Resumen de la demostracion (orden recomendado en clase)
1. `docker compose up -d --build` y `docker compose ps`  (todo arriba)
2. `whoami` x6  -> balanceo
3. `ping` entre contenedores  -> comunicacion
4. `stop web01` / `whoami`  -> alta disponibilidad (failover)
5. `run_tests.py`  -> 12/12 pruebas
6. backup + restore  -> copias cifradas y recuperacion
7. `logs monitor` + informe SQL  -> monitorizacion y negocio
8. `docker compose down`  -> cierre
