# Guia paso a paso: levantar y demostrar TODO el proyecto con Docker

Esta guia monta el proyecto completo en **una sola maquina con varios contenedores
Docker** (lo que recomendo el profesor) y demuestra su funcionamiento: balanceo,
comunicacion entre componentes, alta disponibilidad (failover), copias de seguridad,
monitorizacion e informes. Todos los comandos son copiar y pegar.

## Que se monta y a que rol de Windows Server equivale

| Contenedor | Rol en el contenedor | Equivalente en el diseno (Windows Server) |
|------------|----------------------|-------------------------------------------|
| `lb`     | Balanceador / proxy inverso (nginx) | LB01 / NLB en Windows Server |
| `web01`  | Servidor web + aplicacion           | WEB01 con IIS |
| `web02`  | Servidor web + aplicacion (replica) | WEB02 con IIS |
| volumen `dbdata` | Base de datos compartida    | SQL01 + Listener (SQL Server Always On) |
| `monitor`| Metricas y disponibilidad           | PerfMon + PRTG |

Los contenedores se comunican por una **red interna de Docker** llamada `backend`
(equivale a la VLAN del diseno). Se hablan por su nombre: `web01`, `web02`, `lb`.

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
En Windows PowerShell, si `curl` da problemas, usa:
```powershell
1..6 | % { (Invoke-WebRequest -Uri https://localhost/whoami -SkipCertificateCheck).Content }
```
**Que demuestra:** el balanceador reparte las peticiones entre los dos servidores web.

---

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
y comparten el almacenamiento de datos (igual que WEB01/WEB02 hablan con el Listener SQL).

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

## 10. (Opcional, avanzado) Demostrar con un SQL Server real

El diseno corporativo usa Microsoft SQL Server. Si quieres ensenar un SQL Server real
en contenedor (Linux), puedes anadir este servicio en una prueba aparte:

```yaml
  sqlserver:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      ACCEPT_EULA: "Y"
      MSSQL_SA_PASSWORD: "Cl4veFuerte!2025"
    ports: [ "1433:1433" ]
    networks: [ backend ]
```
Y aplicar el guion `db/sqlserver-setup.sql` (TDE, usuarios y Listener):
```bash
docker compose exec sqlserver /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'Cl4veFuerte!2025' -i /db/sqlserver-setup.sql
```
> Nota: para que la aplicacion use SQL Server en lugar de SQLite habria que cambiar la
> cadena de conexion y el driver; en el laboratorio se mantiene SQLite por simplicidad y
> reproducibilidad. Este paso solo demuestra que el SQL Server real arranca y acepta el
> esquema con cifrado.

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
