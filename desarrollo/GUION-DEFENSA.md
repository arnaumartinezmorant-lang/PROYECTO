# Guion de defensa y demostracion (paso a paso)

Guion para presentar el proyecto en clase. Duracion aproximada: 8-10 minutos.
Antes de empezar: abre una terminal en la carpeta `desarrollo/`.

> Opcion A (recomendada para la demo en vivo): `bash run-lab.sh` lo ejecuta TODO de
> seguido y deja las evidencias en `evidencias/`. Las opciones B explican como
> hacer cada parte por separado, por si el profesor pide ver algo concreto.

---

## 0. Introduccion (30 s) — que se va a ver
Frase de apertura sugerida:
> "Disenamos una infraestructura corporativa (dominio, alta disponibilidad, copias y
> sistema de incidencias). Como el montaje con muchas maquinas no era demostrable, lo
> implementamos de forma simplificada pero funcional con una sola maquina y varios
> contenedores Docker. Os lo ensenamos funcionando y con evidencias."

Enseña el apartado **11.5** de la memoria (plan unico de IPs/VLANs/servidores).

---

## 1. Arrancar el sistema (1 min)
```bash
docker compose up -d --build      # opcion con contenedores
# o, sin Docker:
bash run-lab.sh                   # arranca todo y genera evidencias
```
Que decir: "Levantamos el balanceador, dos servidores web y la base de datos."

## 2. Demostrar el balanceo de carga (1 min)
```bash
# con Docker:
for i in $(seq 1 6); do curl -sk https://localhost/whoami; echo; done
# en el lab sin Docker (puerto 18080):
NO_PROXY=127.0.0.1 BASE_URL=http://127.0.0.1:18080 python3 pruebas/whoami_sampler.py 6
```
Que mostrar: las respuestas alternan entre **WEB01** y **WEB02**.
Evidencia: `evidencias/salidas/02-balanceo.txt`.

## 3. Demostrar la ALTA DISPONIBILIDAD / failover (2 min) — lo mas importante
```bash
docker compose stop web01     # apagamos un nodo a proposito
for i in $(seq 1 4); do curl -sk https://localhost/whoami; echo; done   # sigue: WEB02
docker compose start web01    # lo recuperamos
```
Que decir: "Apagamos WEB01 y el servicio NO se cae: lo atiende WEB02. Al recuperarlo,
vuelve a repartirse la carga." Esto responde al comentario del profesor: no solo se
afirma la continuidad, se **demuestra**. Evidencia: `evidencias/salidas/04-failover.txt`.

## 4. Pruebas de caja negra (1 min)
```bash
BASE_URL=http://127.0.0.1:18080 python3 pruebas/run_tests.py
```
Que mostrar: **12/12 PASAN** (registro, login, validaciones, permisos por rol, historial).
Evidencia: `evidencias/salidas/03-pruebas-caja-negra.txt`.

## 5. Copias de seguridad cifradas + restauracion (1,5 min)
```bash
bash scripts/backup.sh                          # copia 3-2-1 cifrada (AES-256)
bash scripts/restore.sh evidencias/backups/local/*.enc /tmp/restaurada.db
```
Que decir: "Copia local + offsite, cifrada. Al restaurar, `integrity_check = ok`."
Si el profesor duda del cifrado, abre un `.enc`: no se ve texto en claro.
Evidencias: `evidencias/salidas/05-backup.txt` y `06-restore.txt`.

## 6. Monitorizacion e informes (1 min)
```bash
python3 monitor/monitor.py                                  # metricas + disponibilidad
sqlite3 app/data/intranet.db < observabilidad/informes-sql.sql   # informes de negocio
```
Que mostrar: disponibilidad **100 %**; informe de incidencias por estado, tiempo medio
de resolucion y ranking de tecnicos. Evidencias: `08-monitor.txt`, `07-informes-sql.txt`.

## 7. Scripts, cifrado SQL, Listener y GPO (1 min)
Abre y comenta brevemente:
- `db/sqlserver-setup.sql` -> TDE (cifrado), usuarios de minimo privilegio y **Listener**
  Always On (10.10.10.20:1433).
- `scripts/New-EmpleadoAD.ps1` -> alta automatica de usuario en AD con grupo y NTFS.
- `scripts/` -> backup, restore, rotacion de logs, monitor de disco.

## 8. Cierre (30 s)
> "En resumen: red coherente y documentada, sistema funcionando, alta disponibilidad
> demostrada y evidencias que cualquiera puede regenerar con un comando. Las limitaciones
> y el trabajo futuro estan en las Conclusiones."

---

## Preguntas probables y respuesta corta
- **"Por que SQLite y no SQL Server?"** Para que el laboratorio sea reproducible sin
  dependencias. El diseno corporativo es SQL Server con TDE y Always On, y el guion esta
  en `db/sqlserver-setup.sql`. El acceso a datos esta aislado para poder cambiar de motor.
- **"El 3389 estaba mal, ¿como queda?"** Solo se permite RDP/WinRM desde la VLAN 30
  (gestion) o VPN; nunca desde Internet, DMZ ni usuarios (apartado 11.5 y regla R08).
- **"¿Que problema real tuvisteis?"** Al balancear se perdia la sesion; lo resolvimos
  guardando las sesiones en la base de datos compartida.

## Plan B si falla Docker en la demo
Ejecuta `bash run-lab.sh` (no necesita Docker ni Internet) y ensena directamente los
ficheros de `evidencias/salidas/` y `evidencias/EVIDENCIAS.md`.
