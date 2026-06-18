# Plan de direccionamiento y segmentación (fuente única de verdad) — stack Linux

Este documento es la **referencia canónica** del proyecto. Cualquier diagrama, tabla
de reglas de firewall o explicación de la memoria debe coincidir con lo aquí descrito.
Si hay una discrepancia, **manda este documento**.

> Stack: Ubuntu Server 22.04 LTS · Nginx · PostgreSQL 16 · FreeIPA (LDAP + Kerberos + DNS)
> · HAProxy · WireGuard (VPN) · Prometheus/Grafana.

## 1. VLANs y subredes

| VLAN | Nombre / Zona               | Subred           | Gateway (SVI L3) | Nivel de confianza |
|------|-----------------------------|------------------|------------------|--------------------|
| 10   | Backend seguro (servidores) | 10.10.10.0/24    | 10.10.10.1       | Crítico (bajo)     |
| 20   | Usuarios internos (LAN)     | 10.10.20.0/24    | 10.10.20.1       | Medio              |
| 30   | Gestión / Administración    | 10.10.30.0/24    | 10.10.30.1       | Alto (confiable)   |
| 40   | DMZ (servicios publicados)  | 10.10.40.0/24    | 10.10.40.1       | Medio (expuesto)   |
| 99   | WiFi invitados (aislada)    | 10.10.99.0/24    | 10.10.99.1       | No confiable       |

- El enrutamiento inter-VLAN lo hace el **switch L3 / firewall interno** (nftables).
- La VLAN 30 (Gestión) es la **única** que puede abrir **SSH (22)** contra los servidores.
  El teletrabajo de técnicos entra por **VPN (WireGuard)** y se le asigna una IP de la VLAN 30.
- La VLAN 99 (invitados) solo tiene salida a Internet; no enruta a ninguna VLAN interna.

## 2. Inventario de servidores (IP fija)

| Equipo | Rol                                  | VLAN/Zona        | IP            | SO              | Servicios / puertos                     |
|--------|--------------------------------------|------------------|---------------|-----------------|------------------------------------------|
| FW01   | Cortafuegos perimetral + VPN + NAT   | Perímetro        | WAN / 10.10.40.1 | pfSense/nftables | WireGuard 51820/UDP, NAT, reglas FW   |
| LB01   | Balanceador de carga / proxy inverso | DMZ (VLAN 40)    | 10.10.40.10   | Ubuntu 22.04    | Nginx/HAProxy 443 (VIP 10.10.40.5)      |
| WEB01  | Servidor web/aplicación              | DMZ (VLAN 40)    | 10.10.40.11   | Ubuntu 22.04    | Nginx 80/443                            |
| WEB02  | Servidor web/aplicación              | DMZ (VLAN 40)    | 10.10.40.12   | Ubuntu 22.04    | Nginx 80/443                            |
| DC1    | Directorio + DNS (FreeIPA)           | Backend (VLAN 10)| 10.10.10.11   | Ubuntu 22.04    | LDAP/Kerberos/DNS (53,88,389,636)       |
| DC2    | Directorio + DNS (FreeIPA, réplica)  | Backend (VLAN 10)| 10.10.10.12   | Ubuntu 22.04    | LDAP/Kerberos/DNS (53,88,389,636)       |
| SQL01   | Base de datos primaria (PostgreSQL)  | Backend (VLAN 10)| 10.10.10.21   | Ubuntu 22.04    | PostgreSQL 5432 (replicación streaming) |
| SQL02   | Base de datos secundaria (réplica)   | Backend (VLAN 10)| 10.10.10.22   | Ubuntu 22.04    | PostgreSQL 5432 (réplica)               |
| —      | **Endpoint HAProxy (VIP de la BD)**  | Backend (VLAN 10)| **10.10.10.20** | (VIP lógica)  | 5432 (punto de conexión único a la BD)  |
| BKP01  | Servidor de copias de seguridad      | Backend (VLAN 10)| 10.10.10.31   | Ubuntu 22.04    | NFS 2049, repositorio de copias         |

> El **endpoint HAProxy** (10.10.10.20:5432) es el punto único al que apunta la aplicación.
> Si SQL01 cae, Patroni promociona SQL02 y HAProxy redirige las conexiones sin cambiar la
> cadena de conexión de la aplicación (equivale al "Listener" del mundo SQL Server).

## 3. Matriz de puertos / flujos permitidos (resumen)

| Origen                         | Destino                          | Puerto/Protocolo        | Motivo                                   |
|--------------------------------|----------------------------------|-------------------------|------------------------------------------|
| Internet / Usuarios (VLAN 20)  | LB01 (VIP)                       | TCP 443 (HTTPS)         | Acceso web a la intranet                 |
| LB01                           | WEB01 / WEB02                    | TCP 443 (HTTPS)         | Balanceo al pool de frontales            |
| WEB01 / WEB02                  | Endpoint HAProxy (10.10.10.20)   | TCP 5432                | Acceso a datos (PostgreSQL)              |
| WEB01 / WEB02                  | DC1 / DC2 (FreeIPA)              | TCP 636/88/53           | Autenticación (LDAPS/Kerberos) y DNS     |
| SQL01                           | SQL02                             | TCP 5432                | Replicación en streaming                 |
| Servidores                     | BKP01                            | TCP 2049 (NFS)          | Copias de seguridad                      |
| **Gestión (VLAN 30) / VPN**    | **Todos los servidores**         | **TCP 22 (SSH)**        | **Administración remota (solo gestión)** |
| Cualquiera                     | Cualquiera                       | ALL                     | DENY por defecto (default deny)          |

**Nota de seguridad:** la administración remota es **solo por SSH (22)** y **solo con
origen en la VLAN 30 (Gestión)** o desde la VPN WireGuard (que recibe IP de esa VLAN).
Nunca desde Internet, DMZ ni la VLAN de usuarios.

## 4. Equivalencias de diseño (Linux)

| Concepto corporativo | Implementación Linux |
|----------------------|----------------------|
| Directorio + dominio + DNS | FreeIPA (LDAP + Kerberos + BIND) |
| Políticas por rol (tipo GPO) | reglas HBAC y sudo de FreeIPA + Ansible |
| Servidor web | Nginx |
| Base de datos + alta disponibilidad | PostgreSQL + Patroni + HAProxy |
| Cifrado en reposo | LUKS (disco) + pgcrypto (columnas) |
| Cifrado en tránsito | TLS 1.2/1.3 |
| Balanceo / failover del frontal | HAProxy/Nginx + keepalived (VIP) |
| Administración remota | SSH (22) sobre VPN WireGuard |
| Actualizaciones | APT + unattended-upgrades |
| Logs centralizados | rsyslog / journald (opcional ELK) |
| Monitorización | Prometheus + Grafana (node_exporter) |
| Copias de seguridad | pg_dump + rsync + NFS (regla 3-2-1) |
