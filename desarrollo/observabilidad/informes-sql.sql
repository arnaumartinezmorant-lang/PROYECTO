-- Informes de explotacion de la informacion (negocio) sobre la base de incidencias.
-- Compatibles con SQLite (lab) y, con cambios minimos de funciones de fecha, con SQL Server.

-- 1) Incidencias por estado
SELECT estado, COUNT(*) AS total
FROM incidencia
GROUP BY estado
ORDER BY total DESC;

-- 2) Incidencias por prioridad (1=Alta, 2=Media, 3=Baja)
SELECT prioridad, COUNT(*) AS total
FROM incidencia
GROUP BY prioridad
ORDER BY prioridad;

-- 3) Tiempo medio de resolucion (horas) de las incidencias cerradas/resueltas
SELECT ROUND(AVG((julianday(fecha_cierre) - julianday(fecha_creacion)) * 24), 2)
       AS horas_medias_resolucion
FROM incidencia
WHERE fecha_cierre IS NOT NULL;

-- 4) Ranking de tecnicos por nº de incidencias gestionadas
SELECT u.email AS tecnico, COUNT(*) AS gestionadas
FROM incidencia i
JOIN usuario u ON u.id = i.gestor_id
GROUP BY u.email
ORDER BY gestionadas DESC;

-- 5) Trazabilidad: ultimas acciones registradas en el historial
SELECT h.fecha, h.accion, h.comentario, u.email AS autor
FROM historial_incidencia h
JOIN usuario u ON u.id = h.usuario_id
ORDER BY h.id DESC
LIMIT 20;
