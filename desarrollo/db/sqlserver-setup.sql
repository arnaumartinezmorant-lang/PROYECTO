/* ============================================================================
   Diseno corporativo para Microsoft SQL Server 2022 (apartados 14 y 19).
   Incluye: base de datos cifrada con TDE, logins/usuarios con minimo
   privilegio y notas del Availability Group + Listener (Always On).
   Este script documenta y reproduce las afirmaciones de la memoria
   (cifrado SQL, usuarios app_user/backup_user/admin_db, listener SQL).
   ============================================================================ */

-------------------------------------------------------------------------------
-- 1) Cifrado en reposo: Transparent Data Encryption (TDE)
-------------------------------------------------------------------------------
USE master;
GO
-- Clave maestra de servidor (solo una vez por instancia)
CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'Cl4veMaestra$Fuerte!';
GO
-- Certificado que protege la clave de cifrado de la base de datos
CREATE CERTIFICATE TDE_Cert WITH SUBJECT = 'Certificado TDE intranet';
GO
-- IMPORTANTE: respaldar el certificado fuera del servidor (sin el no hay restore)
BACKUP CERTIFICATE TDE_Cert
    TO FILE = 'C:\Backups\TDE_Cert.cer'
    WITH PRIVATE KEY (FILE = 'C:\Backups\TDE_Cert.pvk',
                      ENCRYPTION BY PASSWORD = 'Cl4veCert$Fuerte!');
GO

CREATE DATABASE intranet_corporativa;
GO
USE intranet_corporativa;
GO
-- Clave de cifrado de la BD + activacion de TDE
CREATE DATABASE ENCRYPTION KEY
    WITH ALGORITHM = AES_256
    ENCRYPTION BY SERVER CERTIFICATE TDE_Cert;
GO
ALTER DATABASE intranet_corporativa SET ENCRYPTION ON;
GO
-- Comprobacion (encryption_state = 3 -> cifrada):
-- SELECT db_name(database_id), encryption_state FROM sys.dm_database_encryption_keys;

-------------------------------------------------------------------------------
-- 2) Esquema (equivalente al de init.sql)
-------------------------------------------------------------------------------
CREATE TABLE departamento (
    id INT IDENTITY PRIMARY KEY, nombre NVARCHAR(80) NOT NULL UNIQUE, descripcion NVARCHAR(255));
CREATE TABLE rol (
    id INT IDENTITY PRIMARY KEY, nombre NVARCHAR(40) NOT NULL UNIQUE, nivel INT NOT NULL DEFAULT 1);
CREATE TABLE usuario (
    id INT IDENTITY PRIMARY KEY, nombre NVARCHAR(80) NOT NULL, apellidos NVARCHAR(120) NOT NULL,
    email NVARCHAR(160) NOT NULL UNIQUE, password_hash NVARCHAR(200) NOT NULL,
    departamento_id INT NOT NULL REFERENCES departamento(id),
    estado NVARCHAR(20) NOT NULL DEFAULT 'activo', fecha_alta DATETIME2 NOT NULL DEFAULT SYSDATETIME());
CREATE TABLE usuario_rol (
    usuario_id INT NOT NULL REFERENCES usuario(id), rol_id INT NOT NULL REFERENCES rol(id),
    PRIMARY KEY(usuario_id, rol_id));
CREATE TABLE incidencia (
    id INT IDENTITY PRIMARY KEY, titulo NVARCHAR(160) NOT NULL, descripcion NVARCHAR(MAX) NOT NULL,
    prioridad INT NOT NULL CHECK (prioridad BETWEEN 1 AND 3), estado NVARCHAR(20) NOT NULL DEFAULT 'Abierta',
    creador_id INT NOT NULL REFERENCES usuario(id), gestor_id INT NULL REFERENCES usuario(id),
    fecha_creacion DATETIME2 NOT NULL DEFAULT SYSDATETIME(), fecha_cierre DATETIME2 NULL);
CREATE TABLE historial_incidencia (
    id INT IDENTITY PRIMARY KEY, incidencia_id INT NOT NULL REFERENCES incidencia(id),
    usuario_id INT NOT NULL REFERENCES usuario(id), accion NVARCHAR(40) NOT NULL,
    comentario NVARCHAR(400), fecha DATETIME2 NOT NULL DEFAULT SYSDATETIME());
CREATE TABLE backup (
    id INT IDENTITY PRIMARY KEY, tipo_backup NVARCHAR(40) NOT NULL, fecha DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    resultado NVARCHAR(40) NOT NULL, ubicacion NVARCHAR(260) NOT NULL);
GO

-------------------------------------------------------------------------------
-- 3) Logins / usuarios con MINIMO PRIVILEGIO (apartado 19)
-------------------------------------------------------------------------------
-- app_user: lo usa la aplicacion web (IIS). Solo lectura/escritura de datos.
CREATE LOGIN app_user    WITH PASSWORD = 'App$Pwd2025!';
CREATE LOGIN backup_user WITH PASSWORD = 'Bkp$Pwd2025!';
CREATE LOGIN admin_db    WITH PASSWORD = 'Adm$Pwd2025!';
GO
CREATE USER app_user    FOR LOGIN app_user;
CREATE USER backup_user FOR LOGIN backup_user;
CREATE USER admin_db    FOR LOGIN admin_db;
GO
-- app_user: SELECT/INSERT/UPDATE (no DELETE, no DDL)
GRANT SELECT, INSERT, UPDATE ON SCHEMA::dbo TO app_user;
-- backup_user: solo lectura (db_backupoperator + datareader)
ALTER ROLE db_backupoperator ADD MEMBER backup_user;
ALTER ROLE db_datareader     ADD MEMBER backup_user;
-- admin_db: control total (acceso restringido a la VLAN 30 de gestion por firewall)
ALTER ROLE db_owner ADD MEMBER admin_db;
GO

-------------------------------------------------------------------------------
-- 4) Alta disponibilidad: Always On Availability Group + Listener
-------------------------------------------------------------------------------
/*
  SQL01 (10.10.10.21) = replica primaria, SQL02 (10.10.10.22) = replica secundaria.
  Replicacion sincrona por el puerto 5022; failover automatico.

  CREATE AVAILABILITY GROUP AG_Intranet
     FOR DATABASE intranet_corporativa
     REPLICA ON
        'SQL01' WITH (ENDPOINT_URL='TCP://10.10.10.21:5022',
                      AVAILABILITY_MODE=SYNCHRONOUS_COMMIT, FAILOVER_MODE=AUTOMATIC),
        'SQL02' WITH (ENDPOINT_URL='TCP://10.10.10.22:5022',
                      AVAILABILITY_MODE=SYNCHRONOUS_COMMIT, FAILOVER_MODE=AUTOMATIC);

  -- El LISTENER es el unico punto de conexion para la aplicacion:
  ALTER AVAILABILITY GROUP AG_Intranet
     ADD LISTENER 'sql-intranet' (WITH IP ((N'10.10.10.20', N'255.255.255.0')), PORT=1433);

  La cadena de conexion de la app apunta a:  Server=10.10.10.20,1433  (el Listener),
  de modo que si SQL01 cae, el trafico va a SQL02 sin cambiar la configuracion.
*/
