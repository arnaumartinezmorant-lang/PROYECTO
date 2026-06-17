#!/usr/bin/env python3
"""
Intranet corporativa - Gestion de incidencias (capa de aplicacion).

App web sin dependencias externas (solo libreria estandar de Python) para que el
laboratorio sea 100% reproducible. Implementa las entidades y el control de acceso
por roles (RBAC) descritos en la memoria: Usuario, Departamento, Rol, Incidencia,
Historial_Incidencia y Backup.

Variables de entorno:
  APP_NODE   Nombre del nodo (p. ej. WEB01 / WEB02). Sirve para demostrar el balanceo.
  DB_PATH    Ruta del fichero SQLite. Por defecto ./data/intranet.db
  PORT       Puerto de escucha. Por defecto 8001.

En el diseno corporativo la base de datos es Microsoft SQL Server (ver memoria).
Para el laboratorio reproducible se usa SQLite, que expone el mismo esquema y las
mismas consultas SQL estandar; el codigo de acceso a datos esta aislado en DAO.
"""
import http.server
import socketserver
import json
import os
import sqlite3
import hashlib
import hmac
import secrets
import threading
import time
from urllib.parse import urlparse, parse_qs

APP_NODE = os.environ.get("APP_NODE", "WEB01")
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "intranet.db"))
PORT = int(os.environ.get("PORT", "8001"))

SESSIONS = {}            # token -> {user_id, email, roles}  (cache local opcional)
SESSIONS_LOCK = threading.Lock()
PRIORIDADES = {1, 2, 3}  # 1=Alta, 2=Media, 3=Baja
ESTADOS = {"Abierta", "En curso", "Resuelta", "Cerrada"}


# --------------------------------------------------------------------------- #
# Capa de datos (DAO)
# --------------------------------------------------------------------------- #
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return salt + "$" + dk.hex()


def verify_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    schema_path = os.environ.get(
        "SCHEMA_PATH", os.path.join(os.path.dirname(__file__), "..", "db", "init.sql"))
    conn = get_conn()
    with open(schema_path, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# Logica de negocio
# --------------------------------------------------------------------------- #
def crear_usuario(nombre, apellidos, email, password, departamento="Oficinas", rol="Oficina"):
    conn = get_conn()
    try:
        dep = conn.execute("SELECT id FROM departamento WHERE nombre=?", (departamento,)).fetchone()
        rol_row = conn.execute("SELECT id FROM rol WHERE nombre=?", (rol,)).fetchone()
        if dep is None or rol_row is None:
            return None, "Departamento o rol inexistente"
        cur = conn.execute(
            "INSERT INTO usuario(nombre,apellidos,email,password_hash,departamento_id,estado) "
            "VALUES(?,?,?,?,?, 'activo')",
            (nombre, apellidos, email, hash_password(password), dep["id"]),
        )
        uid = cur.lastrowid
        conn.execute("INSERT INTO usuario_rol(usuario_id, rol_id) VALUES(?,?)", (uid, rol_row["id"]))
        conn.commit()
        return uid, None
    except sqlite3.IntegrityError:
        return None, "El correo ya existe"
    finally:
        conn.close()


def roles_de(uid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT r.nombre FROM rol r JOIN usuario_rol ur ON ur.rol_id=r.id WHERE ur.usuario_id=?",
        (uid,),
    ).fetchall()
    conn.close()
    return [r["nombre"] for r in rows]


def crear_sesion(uid):
    token = secrets.token_hex(24)
    conn = get_conn()
    conn.execute("INSERT INTO sesion(token, usuario_id) VALUES(?,?)", (token, uid))
    conn.commit()
    conn.close()
    return token


def sesion_por_token(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute("SELECT usuario_id FROM sesion WHERE token=?", (token,)).fetchone()
    conn.close()
    if not row:
        return None
    uid = row["usuario_id"]
    return {"uid": uid, "roles": roles_de(uid)}


def autenticar(email, password):
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuario WHERE email=?", (email,)).fetchone()
    conn.close()
    if row and row["estado"] == "activo" and verify_password(password, row["password_hash"]):
        return row["id"]
    return None


def crear_incidencia(uid, titulo, descripcion, prioridad):
    if not titulo or not descripcion:
        return None, "Los campos titulo y descripcion son obligatorios"
    if prioridad not in PRIORIDADES:
        return None, "Prioridad fuera de rango (1-3)"
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO incidencia(titulo,descripcion,prioridad,estado,creador_id,fecha_creacion) "
        "VALUES(?,?,?, 'Abierta', ?, datetime('now'))",
        (titulo, descripcion, prioridad, uid),
    )
    iid = cur.lastrowid
    conn.execute(
        "INSERT INTO historial_incidencia(incidencia_id,usuario_id,accion,comentario,fecha) "
        "VALUES(?,?,?,?,datetime('now'))",
        (iid, uid, "creacion", "Incidencia creada"),
    )
    conn.commit()
    conn.close()
    return iid, None


def cambiar_estado(uid, iid, nuevo_estado):
    if "Tecnico" not in roles_de(uid):
        return False, "Permisos insuficientes: se requiere rol Tecnico"
    if nuevo_estado not in ESTADOS:
        return False, "Estado no valido"
    conn = get_conn()
    inc = conn.execute("SELECT id FROM incidencia WHERE id=?", (iid,)).fetchone()
    if inc is None:
        conn.close()
        return False, "Incidencia inexistente"
    conn.execute(
        "UPDATE incidencia SET estado=?, gestor_id=?, "
        "fecha_cierre=CASE WHEN ? IN ('Resuelta','Cerrada') THEN datetime('now') ELSE NULL END "
        "WHERE id=?",
        (nuevo_estado, uid, nuevo_estado, iid),
    )
    conn.execute(
        "INSERT INTO historial_incidencia(incidencia_id,usuario_id,accion,comentario,fecha) "
        "VALUES(?,?,?,?,datetime('now'))",
        (iid, uid, "cambio_estado", "Estado -> " + nuevo_estado),
    )
    conn.commit()
    conn.close()
    return True, None


def listar_incidencias():
    conn = get_conn()
    rows = conn.execute(
        "SELECT i.id,i.titulo,i.prioridad,i.estado,u.email AS creador "
        "FROM incidencia i JOIN usuario u ON u.id=i.creador_id ORDER BY i.id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def historial(iid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT accion,comentario,fecha FROM historial_incidencia WHERE incidencia_id=? ORDER BY id",
        (iid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Servidor HTTP
# --------------------------------------------------------------------------- #
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "IntranetCorp/1.0"

    def log_message(self, fmt, *args):
        # Log accesible (formato tipo IIS) hacia stdout -> se recoge como evidencia
        print("%s - %s [%s] node=%s %s" % (
            self.client_address[0], "-", self.log_date_time_string(), APP_NODE, fmt % args))

    # ---- utilidades ---- #
    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Served-By", APP_NODE)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {k: v[0] for k, v in parse_qs(raw.decode()).items()}

    def _session(self):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            if "sid=" in part:
                token = part.split("sid=")[-1].strip()
                return sesion_por_token(token)
        return None

    # ---- routing ---- #
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, b"OK", "text/plain")
        if path == "/whoami":
            return self._send(200, {"node": APP_NODE})
        if path == "/" or path == "/index.html":
            return self._send(200, INDEX_HTML.replace("__NODE__", APP_NODE).encode(), "text/html")
        if path == "/api/incidencias":
            if not self._session():
                return self._send(401, {"error": "No autenticado"})
            return self._send(200, {"node": APP_NODE, "incidencias": listar_incidencias()})
        if path.startswith("/api/incidencias/") and path.endswith("/historial"):
            if not self._session():
                return self._send(401, {"error": "No autenticado"})
            try:
                iid = int(path.split("/")[3])
            except (ValueError, IndexError):
                return self._send(404, {"error": "Incidencia no valida"})
            return self._send(200, {"historial": historial(iid)})
        return self._send(404, {"error": "No encontrado"})

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._body()

        if path == "/api/registro":
            for campo in ("nombre", "apellidos", "email", "password"):
                if not data.get(campo):
                    return self._send(400, {"error": "Faltan campos obligatorios"})
            uid, err = crear_usuario(
                data["nombre"], data["apellidos"], data["email"], data["password"],
                data.get("departamento", "Oficinas"), data.get("rol", "Oficina"))
            if err:
                return self._send(409, {"error": err})
            return self._send(201, {"id": uid, "mensaje": "Usuario registrado"})

        if path == "/api/login":
            uid = autenticar(data.get("email", ""), data.get("password", ""))
            if not uid:
                return self._send(401, {"error": "Error de acceso"})
            token = crear_sesion(uid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", "sid=%s; HttpOnly; Path=/" % token)
            payload = json.dumps({"mensaje": "Login correcto", "roles": roles_de(uid)}).encode()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        sess = self._session()
        if path == "/api/logout":
            return self._send(200, {"mensaje": "Sesion cerrada"})

        if path == "/api/incidencias":
            if not sess:
                return self._send(401, {"error": "No autenticado"})
            try:
                prioridad = int(data.get("prioridad", 0))
            except (TypeError, ValueError):
                prioridad = 0
            iid, err = crear_incidencia(sess["uid"], data.get("titulo", ""),
                                        data.get("descripcion", ""), prioridad)
            if err:
                return self._send(400, {"error": err})
            return self._send(201, {"id": iid, "mensaje": "Incidencia creada"})

        if path.startswith("/api/incidencias/") and path.endswith("/estado"):
            if not sess:
                return self._send(401, {"error": "No autenticado"})
            try:
                iid = int(path.split("/")[3])
            except (ValueError, IndexError):
                return self._send(404, {"error": "Incidencia no valida"})
            ok, err = cambiar_estado(sess["uid"], iid, data.get("estado", ""))
            if not ok:
                return self._send(403, {"error": err})
            return self._send(200, {"mensaje": "Estado actualizado"})

        return self._send(404, {"error": "No encontrado"})


INDEX_HTML = """<!doctype html><html lang=es><head><meta charset=utf-8>
<title>Intranet Corporativa - Gestion de Incidencias</title>
<style>body{font-family:sans-serif;margin:40px;background:#f4f6f8}
h1{color:#1d3557}.node{color:#457b9d;font-weight:bold}</style></head>
<body><h1>Intranet Corporativa &mdash; Gestion de Incidencias</h1>
<p>Servido por el nodo <span class=node>__NODE__</span> a traves del balanceador de carga.</p>
<p>API REST disponible en <code>/api/...</code>. Estado del nodo: <code>/health</code>.</p>
</body></html>"""


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    init_db()
    httpd = ThreadingServer(("0.0.0.0", PORT), Handler)
    print("[%s] Nodo %s escuchando en :%d (DB=%s)" % (time.strftime("%H:%M:%S"), APP_NODE, PORT, DB_PATH))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
