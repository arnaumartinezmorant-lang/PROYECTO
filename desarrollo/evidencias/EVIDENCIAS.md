# Evidencias de la ejecución del laboratorio

Todas las salidas de esta carpeta se generan ejecutando `bash run-lab.sh`. Son la
prueba objetiva de que el proyecto **funciona y se puede demostrar**. Fecha de la
ejecución de referencia: 16/06/2026.

| Nº | Evidencia | Fichero | Resultado resumido |
|----|-----------|---------|--------------------|
| 1 | Alta de usuarios y datos demo | `salidas/01-seed.txt` | 3 usuarios (Técnico/Admin/Oficina) + 7 incidencias |
| 2 | Reparto de carga | `salidas/02-balanceo.txt` | 6 peticiones → WEB01=3, WEB02=3 |
| 3 | Pruebas de caja negra | `salidas/03-pruebas-caja-negra.txt` | **12 / 12 PASAN** |
| 4 | Failover (alta disponibilidad) | `salidas/04-failover.txt` | Se apaga WEB01 → el servicio sigue por WEB02 → al volver, rebalancea |
| 5 | Copia de seguridad 3-2-1 cifrada | `salidas/05-backup.txt` | Copia local + offsite, AES-256, registrada en BD |
| 6 | Restauración (RTO) | `salidas/06-restore.txt` | `integrity_check = ok`, 4 usuarios recuperados |
| 7 | Informes de explotación (SQL) | `salidas/07-informes-sql.txt` | Tiempo medio de resolución ≈ 6,12 h; ranking de técnicos; cifrado verificado |
| 8 | Monitorización | `salidas/08-monitor.txt` | Disponibilidad = **100 %** (objetivo ≥ 99 %) |
| 9 | Monitorización de disco | `salidas/09-disco.txt` | Uso por punto de montaje + alerta por umbral |
| - | Logs de acceso de los nodos | `logs/web01.log`, `logs/web02.log`, `logs/lb.log` | Peticiones HTTP por nodo (formato tipo IIS) |
| - | Copias cifradas | `backups/local/*.enc`, `backups/offsite/*.enc` | Ficheros binarios cifrados (sin texto en claro) |

## Métricas clave (medidas, no estimadas)

- **Pruebas funcionales:** 12 casos de caja negra, 12 superados (0 fallos).
- **Disponibilidad:** 100 % sobre 15 muestras durante la monitorización; el servicio
  se mantiene durante la caída de un nodo (failover demostrado).
- **Reparto de carga:** 50 % / 50 % entre los dos frontales en condiciones normales.
- **Recuperación:** RTO medido de la restauración por debajo de 1 s en el lab;
  `integrity_check = ok` tras restaurar desde copia cifrada.
- **Negocio:** 7 incidencias gestionadas, tiempo medio de resolución ≈ 6,12 h.

> Para volver a generar estas evidencias en cualquier equipo: `bash run-lab.sh`.
