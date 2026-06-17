#!/usr/bin/env python3
"""Crea los usuarios iniciales del laboratorio (datos de demostracion)."""
import os
import app as a

USERS = [
    # nombre, apellidos, email, password, departamento, rol
    ("Laura", "Gomez",  "tecnico@corp.local", "Tecnico123!",  "Soporte",        "Tecnico"),
    ("Marc",  "Soler",  "admin@corp.local",   "Admin123!",    "Administracion", "Administracion"),
    ("Ana",   "Ruiz",   "oficina@corp.local", "Oficina123!",  "Oficinas",       "Oficina"),
]


def main():
    a.init_db()
    ids = {}
    for nombre, apellidos, email, pwd, dep, rol in USERS:
        uid, err = a.crear_usuario(nombre, apellidos, email, pwd, dep, rol)
        if err:
            print("  [=] %s ya existe (%s)" % (email, err))
        else:
            ids[email] = uid
            print("  [+] usuario %s creado (rol %s, id=%d)" % (email, rol, uid))
    sembrar_incidencias_demo()


def sembrar_incidencias_demo():
    """Carga incidencias historicas con fechas realistas para que los informes
    de explotacion muestren metricas con sentido (tiempo medio de resolucion, etc.)."""
    conn = a.get_conn()
    ya = conn.execute("SELECT COUNT(*) c FROM incidencia").fetchone()["c"]
    if ya:
        conn.close()
        return
    of = conn.execute("SELECT id FROM usuario WHERE email='oficina@corp.local'").fetchone()
    ad = conn.execute("SELECT id FROM usuario WHERE email='admin@corp.local'").fetchone()
    te = conn.execute("SELECT id FROM usuario WHERE email='tecnico@corp.local'").fetchone()
    if not (of and te):
        conn.close()
        return
    demo = [
        # titulo, prioridad, creador, horas_hasta_resolver (None = sigue abierta)
        ("No tengo acceso a la carpeta compartida", 2, of["id"], 3.5),
        ("El equipo va muy lento al arrancar", 3, ad["id"], 26.0),
        ("Error al conectar a la VPN desde casa", 1, te["id"], 1.0),
        ("Impresora de planta 2 sin conexion", 2, of["id"], 5.5),
        ("Solicitud de alta de nuevo usuario", 3, ad["id"], None),
        ("Caida intermitente del portal web", 1, of["id"], 0.75),
    ]
    for titulo, prio, creador, horas in demo:
        cur = conn.execute(
            "INSERT INTO incidencia(titulo,descripcion,prioridad,estado,creador_id,gestor_id,"
            "fecha_creacion,fecha_cierre) VALUES(?,?,?,?,?,?, datetime('now','-7 days'), ?)",
            (titulo, "Incidencia de ejemplo: " + titulo, prio,
             "Cerrada" if horas is not None else "Abierta", creador,
             te["id"] if horas is not None else None, None))
        iid = cur.lastrowid
        if horas is not None:
            conn.execute(
                "UPDATE incidencia SET fecha_cierre=datetime(fecha_creacion, ?) WHERE id=?",
                ("+%d minutes" % int(horas * 60), iid))
        conn.execute(
            "INSERT INTO historial_incidencia(incidencia_id,usuario_id,accion,comentario,fecha) "
            "VALUES(?,?,?,?,datetime('now','-7 days'))",
            (iid, creador, "creacion", "Incidencia creada"))
        if horas is not None:
            conn.execute(
                "INSERT INTO historial_incidencia(incidencia_id,usuario_id,accion,comentario,fecha) "
                "VALUES(?,?,?,?,datetime('now','-7 days'))",
                (iid, te["id"], "cambio_estado", "Estado -> Cerrada"))
    conn.commit()
    conn.close()
    print("  [+] %d incidencias de demostracion cargadas" % len(demo))


if __name__ == "__main__":
    main()
