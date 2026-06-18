# Como dibujar los diagramas (apartados 10 y 11) en draw.io

Todos los valores (IPs, VLANs, puertos) salen del apartado 11.5 / plan-direccionamiento.md.
**Usa SIEMPRE estos mismos valores en todos los diagramas** para que sean coherentes.

Datos canonicos (cópialos tal cual en las etiquetas):
- VLAN 10 Backend `10.10.10.0/24` | VLAN 20 Usuarios `10.10.20.0/24` | VLAN 30 Gestion `10.10.30.0/24`
  | VLAN 40 DMZ `10.10.40.0/24` | VLAN 99 WiFi invitados `10.10.99.0/24`
- LB01 `10.10.40.10` (VIP `10.10.40.5`) | WEB01 `10.10.40.11` | WEB02 `10.10.40.12`
- DC1 `10.10.10.11` | DC2 `10.10.10.12` | SQL01 `10.10.10.21` | SQL02 `10.10.10.22`
  | endpoint HAProxy `10.10.10.20` | BKP01 `10.10.10.31`
- Puertos: HTTPS 443 | SQL 5432 | LDAPS 636 | DNS 53 | Kerberos 88 | NFS 2049 | replica AG 5432
  | SSH 22 y SSH 22 (SOLO desde VLAN 30)

Consejo draw.io: menu **More Shapes... > Networking** (activa "Cisco", "Networking/Rack")
para tener iconos de router, firewall, switch y servidor. Colorea cada VLAN de un color.

---

## Apartado 10 - Esbozo de la arquitectura (vista general, sencilla)
Vista de alto nivel: quien habla con quien, con protocolo/puerto en las lineas.

```
        [ Internet ]                 [ Usuarios internos VLAN20 ]
             |  HTTPS 443                     |  HTTPS 443
             v                                v
        +---------------------- FW01 (Firewall + VPN) ----------------------+
                                   |  443
                                   v
                            [ LB01 Balanceador ]  (VIP 10.10.40.5)
                              /                \   HTTPS 443
                             v                  v
                     [ WEB01 ]              [ WEB02 ]   (DMZ VLAN40)
                             \                  /
                              \  5432 (endpoint HAProxy)/
                               v              v
                        [ endpoint HAProxy 10.10.10.20 ]
                          /                    \   5432 (replica)
                         v                      v
                  [ SQL01 ]  <--- AG --->  [ SQL02 ]   (Backend VLAN10)
                         |  445 (NFS)
                         v
                  [ BKP01 Backup ] ---> copia offsite cifrada
   [ DC1 ] [ DC2 ]  (FreeIPA + DNS, VLAN10)  <-- 636/88/53 desde WEB01/WEB02
   Administracion/DevOps (VLAN30 / VPN) ---22/22---> todos los servidores
```
Pasos:
1. Caja "Internet" (nube) arriba a la izquierda; caja "Usuarios internos (VLAN20)" arriba derecha.
2. Firewall FW01 en el centro-arriba. Flechas desde Internet y Usuarios al FW con etiqueta "HTTPS 443".
3. Debajo, LB01 (rectangulo). Flecha FW01 -> LB01 "443". Pon "VIP 10.10.40.5".
4. Dos cajas WEB01 y WEB02 bajo el LB. Flechas LB->WEB01 y LB->WEB02 con "HTTPS 443".
5. Caja "endpoint HAProxy 10.10.10.20". Flechas WEB01->endpoint HAProxy y WEB02->endpoint HAProxy con "5432".
6. SQL01 y SQL02 bajo el endpoint HAProxy; flecha doble entre ellos "AG replica 5432".
7. BKP01 a un lado; flecha SQL01->BKP01 "NFS 2049" y BKP01-> "offsite cifrado".
8. DC1 y DC2 en un grupo; flecha WEB01/WEB02 -> DC "636/88/53".
9. Caja "Administracion/DevOps (VLAN30/VPN)"; flecha hacia los servidores con "SSH 22".

---

## Apartado 11.1 - Diagrama de CONTEXTO (sistema como caja negra + actores)
Un circulo/recuadro central "SISTEMA INTRANET CORPORATIVA" y los actores alrededor con flechas
etiquetadas (que pide/recibe cada uno). NO se ven servidores aqui, solo el sistema y los actores.

```
     [Usuarios Externos] --HTTPS: consulta web--> ( SISTEMA INTRANET ) --respuesta web-->
     [Usuarios Internos] --crea/consulta incidencias-->
     [Administracion/DevOps] --gestion (VPN, SSH)-->
     [Servicios externos] <--correo/notificaciones-->
```
Pasos:
1. Recuadro grande central con el nombre del sistema.
2. Cuatro actores (monigotes o cajas): Usuarios Externos, Usuarios Internos, Administracion/DevOps,
   Servicios externos.
3. Flechas bidireccionales con la accion (no pongas IPs aqui, es vista funcional).

---

## Apartado 11.2 - Diagrama de COMPONENTES (capas internas)
Muestra las "piezas de software" y como dependen entre si (no IPs, si protocolos).

```
   [Navegador]
        | HTTPS 443
   [Balanceador / Proxy inverso]
        | HTTP/HTTPS
   [Servidor web/aplicacion (x2)] --LDAPS 636--> [FreeIPA / DNS]
        | 5432
   [Acceso a datos (endpoint HAProxy)]
        |
   [Base de datos PostgreSQL]
        |
   [Subsistema de copias 3-2-1 + cifrado]
```
Pasos: cajas apiladas por capas (presentacion -> balanceo -> aplicacion -> datos), con flechas
etiquetadas por protocolo. A un lado, los componentes transversales: "AD/DNS", "Backup/cifrado",
"Monitorizacion".

---

## Apartado 11.3 - Diagrama de RED (el mas importante; aqui SI van VLANs, IPs y puertos)
Dibuja cajas/rectangulos por VLAN (cada una de un color) y mete dentro sus equipos con su IP.
El switch L3 / firewall enruta entre VLANs.

```
                              ( Internet )
                                   |
                          [ FW01 Firewall + VPN ]
                                   |
                        [ Switch L3 / enrutamiento inter-VLAN ]
   ________________________________|________________________________________
  |                 |                         |                              |
VLAN40 DMZ        VLAN20 Usuarios          VLAN10 Backend                 VLAN30 Gestion
10.10.40.0/24     10.10.20.0/24            10.10.10.0/24                  10.10.30.0/24
+-------------+   +---------------+   +---------------------------+   +----------------+
| LB01 .40.10 |   | PCs usuarios  |   | DC1 .10.11   DC2 .10.12   |   | Admin/DevOps   |
| (VIP .40.5) |   | (DHCP)        |   | SQL01 .10.21 SQL02 .10.22 |   | + VPN tecnicos |
| WEB01 .40.11|   |               |   | endpoint HAProxy .10.20 (5432)    |   |  SSH 22      |
| WEB02 .40.12|   |               |   | BKP01 .10.31              |   |  SSH 22    |
+-------------+   +---------------+   +---------------------------+   +----------------+
        (VLAN99 WiFi invitados 10.10.99.0/24: aislada, solo salida a Internet)
```
Etiqueta las lineas principales con el puerto:
- Internet/Usuarios -> LB01: **443**
- LB01 -> WEB01/WEB02: **443**
- WEB01/WEB02 -> endpoint HAProxy(.10.20): **5432**
- WEB01/WEB02 -> DC1/DC2: **636 / 88 / 53**
- SQL01 <-> SQL02: **5432** (replica AG)
- Servidores -> BKP01: **445**
- VLAN30/VPN -> todos los servidores: **22 / 22** (y SOLO desde aqui)
Pasos:
1. Nube Internet arriba -> FW01 -> Switch L3 (un rectangulo ancho).
2. Del switch salen 5 contenedores (uno por VLAN), cada uno de un color, con su subred como titulo.
3. Dentro de cada VLAN, las cajas de servidores con su IP exacta.
4. Dibuja las flechas con los puertos de la lista. Marca en rojo o con un candado la regla
   "22/22 solo desde VLAN 30".

---

## Apartado 11.4 - Diagrama de FLUJO DE DATOS (recorrido de una peticion)
Numerado, sigue el dato desde el usuario hasta la base de datos y la respuesta.

```
1) Usuario --HTTPS 443--> 2) LB01 (elige WEB01 o WEB02)
3) WEBxx --valida usuario (LDAPS 636)--> DC1/DC2
4) WEBxx --consulta/escribe (5432)--> endpoint HAProxy --> SQL01 (activo)
5) SQL01 --replica (5432)--> SQL02     6) SQL01 --backup (445)--> BKP01 --> offsite cifrado
7) WEBxx --respuesta HTTPS--> LB01 --> Usuario
   (si WEB01 cae: el LB manda todo a WEB02; si SQL01 cae: el endpoint HAProxy apunta a SQL02)
```
Pasos: cajas en secuencia con flechas numeradas (1..7) y el puerto en cada flecha. Añade dos notas
de failover (WEB y SQL) para enlazar con la prueba de alta disponibilidad.

---

## Recomendaciones finales
- Mismo color por VLAN en TODOS los diagramas (p. ej. DMZ naranja, Backend azul, Gestion verde,
  Usuarios gris, Invitados amarillo).
- Pon una leyenda pequena con los colores de VLAN.
- Exporta cada diagrama como PNG (Archivo > Exportar como > PNG, fondo blanco) y sustituye las
  imagenes antiguas de los apartados 10 y 11 en la memoria.
- Revisa que cada IP/puerto del dibujo coincide EXACTAMENTE con la tabla del apartado 11.5.
