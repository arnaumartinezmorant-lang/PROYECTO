#!/usr/bin/env python3
"""
Balanceador de carga / proxy inverso en Python (solo libreria estandar).

Se usa para el laboratorio reproducible cuando no se dispone de nginx, y para
generar la evidencia de la prueba de failover (apartado de Alta Disponibilidad).
Reparte por turnos (round-robin) entre los nodos del pool y los descarta si fallan
el health check, sirviendo desde el nodo sano (conmutacion por error).

Uso:  PORT=8080 BACKENDS=127.0.0.1:8001,127.0.0.1:8002 python3 balanceador.py
"""
import http.server
import socketserver
import os
import threading
import time
import urllib.request

PORT = int(os.environ.get("PORT", "8080"))
BACKENDS = os.environ.get("BACKENDS", "127.0.0.1:8001,127.0.0.1:8002").split(",")
HEALTH = {b: True for b in BACKENDS}
RR = {"i": 0}
LOCK = threading.Lock()


def health_loop():
    while True:
        for b in BACKENDS:
            try:
                with urllib.request.urlopen("http://%s/health" % b, timeout=1) as r:
                    HEALTH[b] = (r.status == 200)
            except Exception:
                HEALTH[b] = False
        time.sleep(2)


def pick_backend():
    with LOCK:
        for _ in range(len(BACKENDS)):
            RR["i"] = (RR["i"] + 1) % len(BACKENDS)
            b = BACKENDS[RR["i"]]
            if HEALTH.get(b):
                return b
    return None


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[LB] %s %s" % (self.log_date_time_string(), fmt % args))

    def _proxy(self):
        if self.path == "/lb-health":
            self.send_response(200); self.send_header("Content-Length", "6"); self.end_headers()
            self.wfile.write(b"LB OK\n"); return
        backend = pick_backend()
        if backend is None:
            self.send_response(503); self.send_header("Content-Length", "0"); self.end_headers()
            print("[LB] 503 - sin backends sanos"); return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        url = "http://%s%s" % (backend, self.path)
        req = urllib.request.Request(url, data=body, method=self.command)
        for h in ("Content-Type", "Cookie", "Authorization"):
            if h in self.headers:
                req.add_header(h, self.headers[h])
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "text/plain"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Upstream", backend)
                if resp.headers.get("Set-Cookie"):
                    self.send_header("Set-Cookie", resp.headers.get("Set-Cookie"))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Upstream", backend)
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            HEALTH[backend] = False
            self.send_response(502); self.send_header("Content-Length", "0"); self.end_headers()
            print("[LB] 502 backend %s caido: %s" % (backend, e))

    do_GET = _proxy
    do_POST = _proxy


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    threading.Thread(target=health_loop, daemon=True).start()
    print("[LB] escuchando en :%d  pool=%s" % (PORT, BACKENDS))
    TS(("0.0.0.0", PORT), Proxy).serve_forever()


if __name__ == "__main__":
    main()
