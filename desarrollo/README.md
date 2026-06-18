# Laboratorio funcional del proyecto de Infraestructura de Red

Este directorio contiene la **implementación real y reproducible** del proyecto.
Siguiendo la recomendación de simplificar para que el proyecto sea funcional y
demostrable, se monta **una sola máquina con varios contenedores Docker** en lugar
de muchas máquinas virtuales. La aplicación es la *intranet de gestión de incidencias*
descrita en la memoria (entidades Usuario, Departamento, Rol, Incidencia,
Historial_Incidencia y Backup) con control de acceso por roles (RBAC).

## Arquitectura del laboratorio

```
                 Internet / Usuarios
                         │  HTTPS 443
                 ┌───────▼────────┐
                 │   lb (nginx)   │  Balanceador / proxy inverso  (rol de LB01 / HAProxy)
                 └───┬───────┬────┘
            ┌────────▼─┐   ┌─▼────────┐
            │  web01   │   │  web02   │  Servidores web/aplicación (Nginx en el diseño)
            └────┬─────┘   └────┬─────┘
                 └──────┬───────┘
                   ┌────▼────┐
                   │   db    │  Base de datos (PostgreSQL en el diseño; SQLite en el lab)
                   └─────────┘
                   ┌─────────┐
                   │ monitor │  Métricas y disponibilidad (Prometheus/Grafana en el diseño)
                   └─────────┘
```

Correspondencia con el diseño corporativo (apartado 11 de la memoria):

| Componente del lab | Rol corporativo | IP de diseño (ver red/plan-direccionamiento.md) |
|--------------------|-----------------|--------------------------------------------------|
| `lb` (nginx)       | LB01 balanceador / HAProxy | 10.10.40.10 (VIP 10.10.40.5) |
| `web01`            | WEB01 (Nginx)     | 10.10.40.11 |
| `web02`            | WEB02 (Nginx)     | 10.10.40.12 |
| `db`               | SQL01 (PostgreSQL, endpoint HAProxy alta disponibilidad (Patroni)) | 10.10.10.20:5432 |
| `monitor`          | Prometheus + Grafana  | VLAN 30 (gestión) |

## Cómo ejecutarlo

### Opción A — Docker (la del enunciado: una VM con contenedores)
```bash
docker compose up -d --build
curl -k https://localhost/whoami      # alterna entre WEB01 y WEB02
docker compose stop web01             # el servicio sigue por WEB02 (failover)
docker compose logs -f lb             # logs del balanceador
```

### Opción B — Laboratorio reproducible sin Docker (genera las evidencias)
No requiere conexión a Internet ni dependencias externas (solo Python 3 y utilidades
estándar). Arranca los dos nodos web + balanceador, ejecuta todas las pruebas y deja
las evidencias en `evidencias/`:
```bash
bash run-lab.sh
```

## Contenido

```
desarrollo/
├── app/            Aplicación web (Python stdlib) + Dockerfile + seed de datos
├── db/             init.sql (SQLite del lab) y postgresql-setup.sql (diseño PostgreSQL: LUKS, usuarios, alta disponibilidad (Patroni))
├── lb/             nginx.conf (Docker) y balanceador.py (equivalente para el lab)
├── monitor/        Agente de monitorización (métricas y disponibilidad)
├── observabilidad/ informes-sql.sql (explotación de la información)
├── scripts/        backup.sh (3-2-1 cifrado), restore.sh, rotate-logs.sh, disk-monitor.sh, new-empleado-ldap.sh
├── pruebas/        run_tests.py (caja negra) y whoami_sampler.py (reparto/failover)
├── red/            plan-direccionamiento.md (FUENTE ÚNICA DE VERDAD de IPs/VLANs/puertos)
├── evidencias/     Salidas reales de la última ejecución (ver EVIDENCIAS.md)
├── docker-compose.yml
└── run-lab.sh      Orquestador del laboratorio reproducible
```

## Decisiones y problemas reales encontrados

- **Sesiones y balanceo:** al repartir con round-robin entre dos nodos, el inicio de
  sesión se perdía porque cada nodo guardaba la sesión en memoria. Se resolvió
  guardando las sesiones en la base de datos compartida (tabla `sesion`), de modo que
  cualquier nodo valida el mismo token. Es el mismo motivo por el que en producción
  se usa estado compartido o afinidad de sesión.
- **Cifrado en reposo:** el laboratorio cifra las copias con AES-256 (gpg). En el
  diseño corporativo el equivalente es LUKS de PostgreSQL (ver `db/postgresql-setup.sql`).
- **Base de datos:** el diseño usa PostgreSQL; para que el lab sea 100%
  reproducible en cualquier equipo se usa SQLite con el mismo esquema y consultas SQL
  estándar. El acceso a datos está aislado para poder cambiar de motor.
