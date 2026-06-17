# Diagramas de la memoria (apartados 10 y 11)

Cada diagrama esta en dos formatos:
- **`.drawio`** — se abre en https://app.diagrams.net (o draw.io de escritorio) para
  editarlo. Para exportar imagen: *Archivo > Exportar como > PNG* (marca "Transparent
  background" desactivado y "Border width" 10).
- **`.svg`** — imagen vectorial lista para usar. En LibreOffice Writer: *Insertar > Imagen*
  y selecciona el `.svg`; queda nitido a cualquier tamano. Tambien se ve en cualquier
  navegador y se puede exportar a PNG.

| Apartado de la memoria | Fichero | Que muestra |
|------------------------|---------|-------------|
| 10. Esbozo de la arquitectura | `10-arquitectura` | Vista general: quien habla con quien y con que puerto |
| 11.1. Diagrama de contexto | `11-1-contexto` | El sistema como caja negra y sus actores |
| 11.2. Diagrama de componentes | `11-2-componentes` | Capas de software (presentacion, balanceo, app, datos) |
| 11.3. Diagrama de red | `11-3-red` | VLANs, IPs y puertos (coherente con el apartado 11.5) |
| 11.4. Diagrama de flujo de datos | `11-4-flujo-datos` | Recorrido numerado de una peticion (1..7) y failover |

## Coherencia
Todos los valores (VLANs, IPs y puertos) coinciden con el apartado **11.5** de la memoria
y con `../plan-direccionamiento.md`. Colores por VLAN: DMZ naranja, Backend azul,
Gestion verde, Usuarios gris, WiFi invitados amarillo.

## Alineacion con la guia de la fase de diseno
Los diagramas siguen lo recomendado en los apuntes de la asignatura (fase de diseno):
nodos principales (servidores, balanceador, router de salida a Internet, firewall),
relaciones entre nodos con su protocolo y puerto, zonas de red (DMZ, red interna y red
de administracion) y actores (usuarios externos, internos y administracion/DevOps).
El esbozo (apartado 10) da la vista general por zonas sin IPs; el diagrama de red
(apartado 11.3) anade el direccionamiento concreto.

## Como sustituir las imagenes antiguas en la memoria
1. Abre `INFRAESTRUCTURA RED.odt` en LibreOffice.
2. Borra la imagen antigua del apartado correspondiente.
3. *Insertar > Imagen* y elige el `.svg` (o el PNG exportado desde draw.io).
4. Ajusta el tamano al ancho de la pagina.
