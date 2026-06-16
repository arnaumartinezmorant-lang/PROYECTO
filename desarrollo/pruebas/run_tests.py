#!/usr/bin/env python3
"""
Plan de pruebas de caja negra REAL ejecutado contra la aplicacion en marcha
(a traves del balanceador de carga). Cada caso indica entrada, salida esperada
y salida real observada, con el codigo HTTP y el cuerpo de la respuesta como
evidencia objetiva. Devuelve codigo de salida != 0 si algun caso falla.

Uso:  BASE_URL=http://127.0.0.1:8080 python3 run_tests.py
"""
import json
import os
import sys
import time
import http.cookiejar
import urllib.request
import urllib.error

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
RESULTS = []


def client():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(opener, method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=5) as r:
            return r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


def check(tc, descripcion, esperado, real, ok):
    RESULTS.append((tc, descripcion, esperado, real, ok))
    estado = "PASA" if ok else "FALLA"
    print("[%s] %-7s %s\n        esperado: %s\n        real:     %s" %
          (estado, tc, descripcion, esperado, real))


def main():
    admin = client()      # sin login -> usado para registro
    tecnico = client()
    oficina = client()

    # TC-01 Registro con datos validos
    st, body, _ = call(admin, "POST", "/api/registro",
                       {"nombre": "Test", "apellidos": "User",
                        "email": "test.user@corp.local", "password": "Test123!"})
    check("TC-01", "Registro de usuario con datos validos",
          "HTTP 201 + mensaje de confirmacion", "HTTP %d %s" % (st, body), st == 201)

    # TC-06 Registro con correo ya existente
    st, body, _ = call(admin, "POST", "/api/registro",
                       {"nombre": "Test", "apellidos": "User",
                        "email": "test.user@corp.local", "password": "Test123!"})
    check("TC-06", "Registro con correo ya existente (rechazado)",
          "HTTP 409 'El correo ya existe'", "HTTP %d %s" % (st, body), st == 409)

    # TC-02 Login con password incorrecta
    st, body, _ = call(tecnico, "POST", "/api/login",
                       {"email": "tecnico@corp.local", "password": "MAL"})
    check("TC-02", "Login con contrasena incorrecta (denegado)",
          "HTTP 401 'Error de acceso'", "HTTP %d %s" % (st, body), st == 401)

    # TC-07 Login con usuario inexistente
    st, body, _ = call(tecnico, "POST", "/api/login",
                       {"email": "noexiste@corp.local", "password": "x"})
    check("TC-07", "Login con usuario inexistente (denegado)",
          "HTTP 401", "HTTP %d %s" % (st, body), st == 401)

    # Login correcto como tecnico y como oficina (necesario para el resto)
    call(tecnico, "POST", "/api/login", {"email": "tecnico@corp.local", "password": "Tecnico123!"})
    call(oficina, "POST", "/api/login", {"email": "oficina@corp.local", "password": "Oficina123!"})

    # TC-03 Crear incidencia con campo obligatorio vacio
    st, body, _ = call(oficina, "POST", "/api/incidencias",
                       {"titulo": "Sin descripcion", "descripcion": "", "prioridad": 2})
    check("TC-03", "Crear incidencia con descripcion vacia (bloqueado)",
          "HTTP 400 campos obligatorios", "HTTP %d %s" % (st, body), st == 400)

    # TC-08 Crear incidencia con prioridad fuera de rango
    st, body, _ = call(oficina, "POST", "/api/incidencias",
                       {"titulo": "Prioridad mala", "descripcion": "x", "prioridad": 9})
    check("TC-08", "Crear incidencia con prioridad no valida (bloqueado)",
          "HTTP 400 prioridad fuera de rango", "HTTP %d %s" % (st, body), st == 400)

    # Crear incidencia valida (precondicion para TC-04/05)
    st, body, _ = call(oficina, "POST", "/api/incidencias",
                       {"titulo": "No imprime", "descripcion": "La impresora no responde", "prioridad": 2})
    iid = json.loads(body).get("id") if st == 201 else None
    check("TC-01b", "Crear incidencia valida",
          "HTTP 201 + id", "HTTP %d %s" % (st, body), st == 201 and iid)

    # TC-04 Cambiar estado por usuario sin rol tecnico
    st, body, _ = call(oficina, "POST", "/api/incidencias/%s/estado" % iid, {"estado": "Resuelta"})
    check("TC-04", "Cambio de estado por usuario sin rol Tecnico (bloqueado)",
          "HTTP 403 permisos insuficientes", "HTTP %d %s" % (st, body), st == 403)

    # TC-04b Cambiar estado por tecnico (permitido)
    st, body, _ = call(tecnico, "POST", "/api/incidencias/%s/estado" % iid, {"estado": "Resuelta"})
    check("TC-04b", "Cambio de estado por Tecnico (permitido)",
          "HTTP 200", "HTTP %d %s" % (st, body), st == 200)

    # TC-05 Consultar historial
    st, body, _ = call(tecnico, "GET", "/api/incidencias/%s/historial" % iid)
    hist = json.loads(body).get("historial", []) if st == 200 else []
    check("TC-05", "Consulta del historial de la incidencia",
          "HTTP 200 + >=2 entradas (creacion y cambio de estado)",
          "HTTP %d con %d entradas" % (st, len(hist)), st == 200 and len(hist) >= 2)

    # TC-10 Acceso sin autenticar
    anon = client()
    st, body, _ = call(anon, "GET", "/api/incidencias")
    check("TC-10", "Acceso a zona privada sin sesion (restringido)",
          "HTTP 401 No autenticado", "HTTP %d %s" % (st, body), st == 401)

    # TC-13 Balanceo de carga: varias peticiones deben repartirse entre WEB01 y WEB02
    nodos = set()
    for _ in range(8):
        st, body, _ = call(client(), "GET", "/whoami")
        try:
            nodos.add(json.loads(body)["node"])
        except Exception:
            pass
        time.sleep(0.05)
    check("TC-13", "Balanceo de carga reparte entre los dos frontales",
          "respuestas servidas por WEB01 y WEB02",
          "nodos observados: %s" % sorted(nodos), {"WEB01", "WEB02"}.issubset(nodos))

    # Resumen
    total = len(RESULTS)
    ok = sum(1 for r in RESULTS if r[4])
    print("\n==================== RESUMEN ====================")
    print("Total casos: %d  |  PASAN: %d  |  FALLAN: %d" % (total, ok, total - ok))
    print("=================================================")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
