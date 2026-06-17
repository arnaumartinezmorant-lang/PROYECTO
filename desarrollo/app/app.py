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


def borrar_sesion(token):
    if not token:
        return
    conn = get_conn()
    conn.execute("DELETE FROM sesion WHERE token=?", (token,))
    conn.commit()
    conn.close()


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


def metricas():
    """Agrega metricas de negocio para el panel (dashboard)."""
    conn = get_conn()

    def scalar(q):
        r = conn.execute(q).fetchone()
        return r[0] if r and r[0] is not None else 0

    tot_u = scalar("SELECT COUNT(*) FROM usuario")
    tot_i = scalar("SELECT COUNT(*) FROM incidencia")
    tot_b = scalar("SELECT COUNT(*) FROM backup")
    abiertas = scalar("SELECT COUNT(*) FROM incidencia WHERE estado NOT IN ('Resuelta','Cerrada')")
    estados = {r["estado"]: r["n"] for r in conn.execute(
        "SELECT estado, COUNT(*) n FROM incidencia GROUP BY estado")}
    prio = {str(r["prioridad"]): r["n"] for r in conn.execute(
        "SELECT prioridad, COUNT(*) n FROM incidencia GROUP BY prioridad")}
    tm = conn.execute(
        "SELECT ROUND(AVG((julianday(fecha_cierre)-julianday(fecha_creacion))*24),2) v "
        "FROM incidencia WHERE fecha_cierre IS NOT NULL").fetchone()["v"]
    ranking = [{"tecnico": r["email"], "n": r["n"]} for r in conn.execute(
        "SELECT u.email, COUNT(*) n FROM incidencia i JOIN usuario u ON u.id=i.gestor_id "
        "GROUP BY u.email ORDER BY n DESC LIMIT 5")]
    conn.close()
    return {"usuarios": tot_u, "incidencias": tot_i, "backups": tot_b, "abiertas": abiertas,
            "por_estado": estados, "por_prioridad": prio,
            "tiempo_medio_horas": tm or 0, "ranking": ranking}


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
        if path == "/api/metricas":
            return self._send(200, metricas())
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
            cookie = self.headers.get("Cookie", "")
            for part in cookie.split(";"):
                if "sid=" in part:
                    borrar_sesion(part.split("sid=")[-1].strip())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", "sid=; HttpOnly; Path=/; Max-Age=0")
            self.send_header("X-Served-By", APP_NODE)
            payload = json.dumps({"mensaje": "Sesion cerrada"}).encode()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

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


INDEX_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Intranet Corporativa - Gestion de Incidencias</title>
<style>
:root{--p:#1d3557;--s:#457b9d;--bg:#eef2f6;--err:#e76f51}
*{box-sizing:border-box}
body{font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:#222}
header{background:var(--p);color:#fff;padding:14px 24px;display:flex;justify-content:space-between;align-items:center}
header h1{font-size:18px;margin:0}
.badge{background:#fff;color:var(--p);border-radius:14px;padding:4px 10px;font-size:12px;font-weight:bold}
main{max-width:1000px;margin:20px auto;padding:0 16px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.12);padding:16px}
.card.full{grid-column:1/3}
h2{font-size:15px;color:var(--p);margin:0 0 10px;border-bottom:1px solid #eee;padding-bottom:6px}
label{display:block;font-size:12px;color:#555;margin:6px 0 2px}
input,select{width:100%;padding:7px;border:1px solid #cbd5e0;border-radius:6px;font-size:13px}
button{background:var(--s);color:#fff;border:0;border-radius:6px;padding:8px 12px;font-size:13px;cursor:pointer;margin-top:8px}
button.sec{background:#6c757d}button.danger{background:var(--err)}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
th,td{border-bottom:1px solid #eee;padding:6px;text-align:left}
th{color:#555}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
#log{font-family:monospace;font-size:12px;background:#0f172a;color:#cbd5e0;border-radius:8px;padding:10px;height:140px;overflow:auto;white-space:pre-wrap}
.pill{padding:2px 8px;border-radius:10px;font-size:11px;color:#fff}
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.kpi{flex:1;min-width:120px;background:#f1f5f9;border-radius:8px;padding:12px;text-align:center}
.kv{font-size:24px;font-weight:bold;color:var(--p)}
.kt{font-size:11px;color:#555;margin-top:2px}
.barrow{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px}
.barrow .bl{width:130px}
.bartrack{flex:1;background:#e9eef3;border-radius:6px;height:16px}
.barfill{height:16px;border-radius:6px;min-width:2px}
</style></head>
<body>
<header><h1>Intranet Corporativa &mdash; Gestion de Incidencias</h1>
<div>Servido por <span class="badge" id="node">__NODE__</span></div></header>
<main>
  <section class="card full">
    <h2>Panel de metricas <button class="sec" style="float:right;margin:0;padding:4px 10px" onclick="panel()">Actualizar</button></h2>
    <div id="kpis" class="kpis"></div>
    <div class="row2">
      <div><b>Incidencias por estado</b><div id="bars" style="margin-top:6px"></div></div>
      <div><b>Ranking de tecnicos (incidencias gestionadas)</b><div id="rank" style="margin-top:6px"></div></div>
    </div>
  </section>
  <section class="card">
    <h2>Acceso</h2>
    <div id="estado">No autenticado.</div>
    <div id="loginbox">
      <label>Correo</label><input id="lemail" placeholder="tecnico@corp.local">
      <label>Contrasena</label><input id="lpass" type="password" placeholder="Tecnico123!">
      <button onclick="login()">Entrar</button>
    </div>
    <button class="danger" id="logoutbtn" style="display:none" onclick="logout()">Cerrar sesion</button>
  </section>
  <section class="card">
    <h2>Registrar usuario</h2>
    <div class="row2"><div><label>Nombre</label><input id="rnom"></div>
      <div><label>Apellidos</label><input id="rape"></div></div>
    <label>Correo</label><input id="remail">
    <label>Contrasena</label><input id="rpass" type="password">
    <div class="row2">
      <div><label>Departamento</label><select id="rdep"><option>Oficinas</option><option>Soporte</option><option>Administracion</option></select></div>
      <div><label>Rol</label><select id="rrol"><option>Oficina</option><option>Tecnico</option><option>Administracion</option></select></div>
    </div>
    <button onclick="registro()">Registrar</button>
  </section>
  <section class="card full">
    <h2>Incidencias</h2>
    <button class="sec" onclick="cargar()">Actualizar lista</button>
    <table id="tabla"><thead><tr><th>ID</th><th>Titulo</th><th>Prioridad</th><th>Estado</th><th>Creador</th><th>Acciones</th></tr></thead><tbody></tbody></table>
    <h2 style="margin-top:14px">Crear incidencia</h2>
    <label>Titulo</label><input id="ctit">
    <label>Descripcion</label><input id="cdesc">
    <label>Prioridad</label><select id="cprio"><option value="1">1 - Alta</option><option value="2" selected>2 - Media</option><option value="3">3 - Baja</option></select>
    <button onclick="crear()">Crear incidencia</button>
  </section>
  <section class="card full"><h2>Actividad (respuestas del servidor)</h2><div id="log"></div></section>
</main>
<script>
let roles=[];
function $(id){return document.getElementById(id);}
function log(m){const l=$('log');l.textContent+=m+"\\n";l.scrollTop=l.scrollHeight;}
async function api(method,path,body){
  const o={method,headers:{}};
  if(body){o.headers['Content-Type']='application/json';o.body=JSON.stringify(body);}
  const r=await fetch(path,o);
  const node=r.headers.get('X-Served-By');if(node)$('node').textContent=node;
  let d={};try{d=await r.json();}catch(e){}
  log('['+method+' '+path+'] -> '+r.status+(node?(' ('+node+')'):'')+' '+JSON.stringify(d));
  return {status:r.status,data:d};
}
async function login(){
  const r=await api('POST','/api/login',{email:$('lemail').value,password:$('lpass').value});
  if(r.status===200){roles=r.data.roles||[];setSesion($('lemail').value);cargar();}
}
async function logout(){await api('POST','/api/logout');roles=[];setSesion(null);
  document.querySelector('#tabla tbody').innerHTML='';}
function setSesion(email){
  if(email){$('estado').innerHTML='Conectado como <b>'+email+'</b> (roles: '+roles.join(', ')+')';
    $('loginbox').style.display='none';$('logoutbtn').style.display='inline-block';}
  else{$('estado').textContent='No autenticado.';$('loginbox').style.display='block';$('logoutbtn').style.display='none';}
}
async function registro(){
  await api('POST','/api/registro',{nombre:$('rnom').value,apellidos:$('rape').value,
    email:$('remail').value,password:$('rpass').value,departamento:$('rdep').value,rol:$('rrol').value});
}
async function crear(){
  await api('POST','/api/incidencias',{titulo:$('ctit').value,descripcion:$('cdesc').value,prioridad:parseInt($('cprio').value)});
  $('ctit').value='';$('cdesc').value='';cargar();
}
const PRIO={1:'Alta',2:'Media',3:'Baja'};
const COLOR={'Abierta':'#e76f51','En curso':'#e9c46a','Resuelta':'#2a9d8f','Cerrada':'#6c757d'};
function kpi(t,v){return '<div class="kpi"><div class="kv">'+v+'</div><div class="kt">'+t+'</div></div>';}
function bar(label,val,total){var w=total?Math.round(100*val/total):0;var c=COLOR[label]||'#457b9d';
  return '<div class="barrow"><span class="bl">'+label+' ('+val+')</span><div class="bartrack">'+
    '<div class="barfill" style="width:'+w+'%;background:'+c+'"></div></div></div>';}
async function panel(){
  const r=await api('GET','/api/metricas');if(r.status!==200)return;const m=r.data;
  $('kpis').innerHTML=kpi('Incidencias',m.incidencias)+kpi('Abiertas',m.abiertas)+
    kpi('Usuarios',m.usuarios)+kpi('Tiempo medio (h)',m.tiempo_medio_horas)+kpi('Copias',m.backups);
  var est=m.por_estado||{};var total=Object.keys(est).reduce(function(a,k){return a+est[k];},0);
  $('bars').innerHTML=Object.keys(est).map(function(e){return bar(e,est[e],total);}).join('')||'(sin datos)';
  $('rank').innerHTML=((m.ranking||[]).map(function(x){return '<div>'+x.tecnico+' &mdash; <b>'+x.n+'</b></div>';}).join(''))||'(sin datos)';
}
async function cargar(){
  const r=await api('GET','/api/incidencias');
  const tb=document.querySelector('#tabla tbody');tb.innerHTML='';
  if(r.status!==200)return;
  (r.data.incidencias||[]).forEach(function(i){
    const tr=document.createElement('tr');
    let acc='<button class="sec" onclick="hist('+i.id+')">Historial</button>';
    if(roles.indexOf('Tecnico')>=0){
      acc+=' <select id="s'+i.id+'"><option>En curso</option><option>Resuelta</option><option>Cerrada</option></select>'+
           ' <button onclick="estado('+i.id+')">Aplicar</button>';
    }
    tr.innerHTML='<td>'+i.id+'</td><td>'+i.titulo+'</td><td>'+(PRIO[i.prioridad]||i.prioridad)+
      '</td><td><span class="pill" style="background:'+(COLOR[i.estado]||'#457b9d')+'">'+i.estado+'</span></td>'+
      '<td>'+i.creador+'</td><td>'+acc+'</td>';
    tb.appendChild(tr);
  });
  panel();
}
async function estado(id){
  await api('POST','/api/incidencias/'+id+'/estado',{estado:$('s'+id).value});cargar();
}
async function hist(id){
  const r=await api('GET','/api/incidencias/'+id+'/historial');
  if(r.status===200){log('  Historial #'+id+':');(r.data.historial||[]).forEach(function(h){
    log('   - '+h.fecha+' | '+h.accion+' | '+(h.comentario||''));});}
}
api('GET','/whoami');panel();
</script>
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
