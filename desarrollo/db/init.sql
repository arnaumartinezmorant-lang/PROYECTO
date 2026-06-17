-- Esquema de la intranet de incidencias (laboratorio reproducible, SQLite).
-- Refleja el modelo entidad-relacion de la memoria (apartados 15-17).
-- El diseno corporativo equivalente para Microsoft SQL Server esta en sqlserver-setup.sql

CREATE TABLE IF NOT EXISTS departamento (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS rol (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL UNIQUE,         -- Tecnico, Administracion, Oficina
    nivel     INTEGER NOT NULL DEFAULT 1    -- nivel de privilegios (1=basico,3=alto)
);

CREATE TABLE IF NOT EXISTS usuario (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    apellidos       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    departamento_id INTEGER NOT NULL REFERENCES departamento(id),
    estado          TEXT NOT NULL DEFAULT 'activo',
    fecha_alta      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usuario_rol (
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    rol_id     INTEGER NOT NULL REFERENCES rol(id),
    PRIMARY KEY (usuario_id, rol_id)
);

CREATE TABLE IF NOT EXISTS incidencia (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo         TEXT NOT NULL,
    descripcion    TEXT NOT NULL,
    prioridad      INTEGER NOT NULL CHECK (prioridad BETWEEN 1 AND 3),
    estado         TEXT NOT NULL DEFAULT 'Abierta',
    creador_id     INTEGER NOT NULL REFERENCES usuario(id),
    gestor_id      INTEGER REFERENCES usuario(id),
    fecha_creacion TEXT NOT NULL DEFAULT (datetime('now')),
    fecha_cierre   TEXT
);

CREATE TABLE IF NOT EXISTS historial_incidencia (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia_id INTEGER NOT NULL REFERENCES incidencia(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id),
    accion        TEXT NOT NULL,
    comentario    TEXT,
    fecha         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backup (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_backup TEXT NOT NULL,
    fecha       TEXT NOT NULL DEFAULT (datetime('now')),
    resultado   TEXT NOT NULL,
    ubicacion   TEXT NOT NULL
);

-- Sesiones compartidas entre los nodos web (estado fuera del proceso) para que
-- el balanceo round-robin no rompa la autenticacion (cualquier nodo valida el token).
CREATE TABLE IF NOT EXISTS sesion (
    token      TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    creada     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Datos de referencia ------------------------------------------------------
INSERT OR IGNORE INTO departamento(nombre, descripcion) VALUES
    ('Administracion', 'Departamento administrativo y financiero'),
    ('Soporte',        'Departamento de soporte tecnico / TI'),
    ('Oficinas',       'Personal de oficina general');

INSERT OR IGNORE INTO rol(nombre, nivel) VALUES
    ('Administracion', 2),
    ('Tecnico',        3),
    ('Oficina',        1);
