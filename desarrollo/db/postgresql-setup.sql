/* ============================================================================
   Diseño corporativo para PostgreSQL 16 (apartados 14 y 19), stack Linux.
   Incluye: cifrado, roles con mínimo privilegio y notas de alta disponibilidad
   (replicación en streaming + Patroni + HAProxy como punto de conexión único).
   ============================================================================ */

-------------------------------------------------------------------------------
-- 1) Cifrado
-------------------------------------------------------------------------------
-- En reposo: el disco/volumen de datos de PostgreSQL va sobre LUKS (cryptsetup).
--   cryptsetup luksFormat /dev/sdb ; mkfs.ext4 /dev/mapper/pgdata ; montar en /var/lib/postgresql
-- En tránsito: TLS obligatorio (postgresql.conf):
--   ssl = on ; ssl_cert_file = 'server.crt' ; ssl_key_file = 'server.key'
-- Columnas sensibles: extensión pgcrypto.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE DATABASE intranet_corporativa;
\connect intranet_corporativa

-------------------------------------------------------------------------------
-- 2) Esquema (equivalente al de init.sql del laboratorio)
-------------------------------------------------------------------------------
CREATE TABLE departamento (
    id SERIAL PRIMARY KEY, nombre VARCHAR(80) NOT NULL UNIQUE, descripcion VARCHAR(255));
CREATE TABLE rol (
    id SERIAL PRIMARY KEY, nombre VARCHAR(40) NOT NULL UNIQUE, nivel INT NOT NULL DEFAULT 1);
CREATE TABLE usuario (
    id SERIAL PRIMARY KEY, nombre VARCHAR(80) NOT NULL, apellidos VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE, password_hash VARCHAR(200) NOT NULL,
    departamento_id INT NOT NULL REFERENCES departamento(id),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo', fecha_alta TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE usuario_rol (
    usuario_id INT NOT NULL REFERENCES usuario(id), rol_id INT NOT NULL REFERENCES rol(id),
    PRIMARY KEY(usuario_id, rol_id));
CREATE TABLE incidencia (
    id SERIAL PRIMARY KEY, titulo VARCHAR(160) NOT NULL, descripcion TEXT NOT NULL,
    prioridad INT NOT NULL CHECK (prioridad BETWEEN 1 AND 3), estado VARCHAR(20) NOT NULL DEFAULT 'Abierta',
    creador_id INT NOT NULL REFERENCES usuario(id), gestor_id INT REFERENCES usuario(id),
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(), fecha_cierre TIMESTAMPTZ);
CREATE TABLE historial_incidencia (
    id SERIAL PRIMARY KEY, incidencia_id INT NOT NULL REFERENCES incidencia(id),
    usuario_id INT NOT NULL REFERENCES usuario(id), accion VARCHAR(40) NOT NULL,
    comentario VARCHAR(400), fecha TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE backup (
    id SERIAL PRIMARY KEY, tipo_backup VARCHAR(40) NOT NULL, fecha TIMESTAMPTZ NOT NULL DEFAULT now(),
    resultado VARCHAR(40) NOT NULL, ubicacion VARCHAR(260) NOT NULL);

-------------------------------------------------------------------------------
-- 3) Roles/usuarios con MÍNIMO PRIVILEGIO (apartado 19)
-------------------------------------------------------------------------------
-- app_user: lo usa la aplicación web (Nginx + app). Solo lectura/escritura de datos.
CREATE ROLE app_user    LOGIN PASSWORD 'App$Pwd2025!';
CREATE ROLE backup_user LOGIN PASSWORD 'Bkp$Pwd2025!';
CREATE ROLE admin_db    LOGIN PASSWORD 'Adm$Pwd2025!' CREATEDB CREATEROLE;

GRANT CONNECT ON DATABASE intranet_corporativa TO app_user, backup_user, admin_db;
GRANT USAGE ON SCHEMA public TO app_user, backup_user;
-- app_user: SELECT/INSERT/UPDATE (sin DELETE ni DDL)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO app_user;
-- backup_user: solo lectura (lo usa pg_dump)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;
-- admin_db: control total (acceso restringido a la VLAN 30 por firewall y por pg_hba.conf)
GRANT ALL PRIVILEGES ON DATABASE intranet_corporativa TO admin_db;

-- Restricción de origen por IP en pg_hba.conf (ejemplo):
--   hostssl intranet_corporativa app_user    10.10.40.0/24  scram-sha-256
--   hostssl intranet_corporativa admin_db    10.10.30.0/24  scram-sha-256

-------------------------------------------------------------------------------
-- 4) Alta disponibilidad: replicación en streaming + Patroni + HAProxy
-------------------------------------------------------------------------------
/*
  DB01 (10.10.10.21) = primaria, DB02 (10.10.10.22) = réplica (streaming, síncrona).
  Patroni gestiona el failover automático; HAProxy publica el ENDPOINT único
  10.10.10.20:5432 que siempre apunta a la primaria activa.

  postgresql.conf (primaria):
     wal_level = replica
     max_wal_senders = 10
     synchronous_commit = on
  La aplicación se conecta SIEMPRE a:  host=10.10.10.20 port=5432  (HAProxy),
  de modo que si DB01 cae, las conexiones van a la nueva primaria sin cambios.

  Comprobación de estado:  patronictl -c /etc/patroni.yml list
*/
