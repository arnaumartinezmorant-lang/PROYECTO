# Plan de direccionamiento y segmentación (fuente única de verdad)

Este documento es la **referencia canónica** del proyecto. Cualquier diagrama, tabla
de reglas de firewall o explicación de la memoria debe coincidir con lo aquí descrito.
Si hay una discrepancia, **manda este documento**.

## 1. VLANs y subredes

| VLAN | Nombre / Zona               | Subred           | Gateway (SVI L3) | Nivel de confianza |
|------|-----------------------------|------------------|------------------|--------------------|
| 10   | Backend seguro (servidores) | 10.10.10.0/24    | 10.10.10.1       | Crítico (bajo)     |
| 20   | Usuarios internos (LAN)     | 10.10.20.0/24    | 10.10.20.1       | Medio              |
| 30   | Gestión / Administración    | 10.10.30.0/24    | 10.10.30.1       | Alto (confiable)   |
| 40   | DMZ (servicios publicados)  | 10.10.40.0/24    | 10.10.40.1       | Medio (expuesto)   |
| 99   | WiFi invitados (aislada)    | 10.10.99.0/24    | 10.10.99.1       | No confiable       |

- El enrutamiento inter-VLAN lo hace el **switch L3 / firewall interno**.
- La VLAN 30 (Gestión) es la **única** que puede abrir RDP (3389) y WinRM (5985)
  contra los servidores. El teletrabajo de técnicos entra por **VPN** y se le asigna
  una IP de la VLAN 30.
- La VLAN 99 (invitados) solo tiene salida a Internet; no enruta a ninguna VLAN interna.

## 2. Inventario de servidores (IP fija)

| Equipo | Rol                                  | VLAN/Zona        | IP            | SO                  | Servicios / puertos que expone        |
|--------|--------------------------------------|------------------|---------------|---------------------|----------------------------------------|
| FW01   | Cortafuegos perimetral + VPN + NAT   | Perímetro        | WAN / 10.10.40.1 | pfSense / WS 2022 | 443 (VPN SSTP), NAT, reglas FW        |
| LB01   | Balanceador de carga / proxy inverso | DMZ (VLAN 40)    | 10.10.40.10   | Windows Server 2022 | 443 (VIP pública 10.10.40.5)          |
| WEB01  | Servidor web frontal                 | DMZ (VLAN 40)    | 10.10.40.11   | Windows Server 2022 | IIS 80/443                            |
| WEB02  | Servidor web frontal                 | DMZ (VLAN 40)    | 10.10.40.12   | Windows Server 2022 | IIS 80/443                            |
| DC1    | Controlador de dominio + DNS         | Backend (VLAN 10)| 10.10.10.11   | Windows Server 2022 | AD DS, DNS (53,88,389,636,445)        |
| DC2    | Controlador de dominio + DNS (réplica)| Backend (VLAN 10)| 10.10.10.12  | Windows Server 2022 | AD DS, DNS (53,88,389,636,445)        |
| SQL01  | Base de datos primaria (Always On)   | Backend (VLAN 10)| 10.10.10.21   | Windows Server 2022 | SQL Server 1433, replicación AG 5022  |
| SQL02  | Base de datos secundaria (Always On) | Backend (VLAN 10)| 10.10.10.22   | Windows Server 2022 | SQL Server 1433, replicación AG 5022  |
| —      | **Listener del Availability Group**  | Backend (VLAN 10)| **10.10.10.20** | (VIP lógica)      | 1433 (punto de conexión único a la BD) |
| BKP01  | Servidor de copias de seguridad      | Backend (VLAN 10)| 10.10.10.31   | Windows Server 2022 | SMB 445, repositorio de backups       |

> El **Listener** (10.10.10.20:1433) es el nombre/IP único al que apunta la aplicación.
> Si SQL01 cae, el listener redirige automáticamente a SQL02 sin cambiar la cadena de conexión.

## 3. Matriz de puertos / flujos permitidos (resumen)

| Origen                         | Destino                         | Puerto/Protocolo        | Motivo                                   |
|--------------------------------|----------------------------------|-------------------------|------------------------------------------|
| Internet / Usuarios (VLAN 20)  | LB01 (VIP)                       | TCP 443 (HTTPS)         | Acceso web a la intranet                 |
| LB01                           | WEB01 / WEB02                    | TCP 443 (HTTPS)         | Balanceo al pool de frontales            |
| WEB01 / WEB02                  | Listener SQL (10.10.10.20)       | TCP 1433                | Acceso a datos                           |
| WEB01 / WEB02                  | DC1 / DC2                        | TCP 636 (LDAPS), 88, 53 | Autenticación y resolución               |
| SQL01                          | SQL02                            | TCP 5022                | Replicación del Availability Group       |
| SQL01 / SQL02 / DC / WEB       | BKP01                            | TCP 445 (SMB)           | Copias de seguridad                      |
| **Gestión (VLAN 30) / VPN**    | **Todos los servidores**         | **TCP 3389 (RDP), 5985 (WinRM)** | **Administración remota (solo desde gestión)** |
| Cualquiera                     | Cualquiera                       | ALL                     | DENY por defecto (default deny)          |

**Corrección clave respecto a la versión anterior:** el puerto **3389 (RDP)** y **5985
(WinRM)** SOLO se permiten con **origen VLAN 30 (Gestión)**. Nunca desde Internet, DMZ
ni VLAN de usuarios. Así se elimina la incoherencia que señaló el profesor.
