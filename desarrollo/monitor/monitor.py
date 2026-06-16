#!/usr/bin/env python3
"""
Agente de monitorizacion (explotacion de la informacion / observabilidad).
Recoge metricas del sistema (CPU, memoria, disco) y comprueba la disponibilidad
de los nodos y del balanceador. Escribe metricas en formato linea y un resumen.
Equivale a PerfMon + sensores PRTG del diseno corporativo.

Variables:  TARGETS (lista coma de URLs /health), ITERS (nº de muestras), INTERVAL.
"""
import os
import time
import urllib.request

TARGETS = os.environ.get(
    "TARGETS", "http://127.0.0.1:8080/lb-health,http://127.0.0.1:8001/health,"
               "http://127.0.0.1:8002/health").split(",")
ITERS = int(os.environ.get("ITERS", "5"))
INTERVAL = float(os.environ.get("INTERVAL", "1"))


def cpu_pct():
    try:
        with open("/proc/stat") as f:
            p = f.readline().split()[1:]
        a = list(map(int, p))
        idle1, tot1 = a[3], sum(a)
        time.sleep(0.2)
        with open("/proc/stat") as f:
            p = f.readline().split()[1:]
        b = list(map(int, p))
        idle2, tot2 = b[3], sum(b)
        dt = tot2 - tot1
        return round(100 * (1 - (idle2 - idle1) / dt), 1) if dt else 0.0
    except Exception:
        return -1.0


def mem_pct():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")[0], line.split()[1]
                info[k] = int(v)
        total, avail = info["MemTotal"], info.get("MemAvailable", info["MemFree"])
        return round(100 * (1 - avail / total), 1)
    except Exception:
        return -1.0


def check(url):
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200, round((time.time() - t0) * 1000, 1)
    except Exception:
        return False, -1.0


def main():
    up = 0
    total = 0
    print("ts,cpu_pct,mem_pct,target,disponible,latencia_ms")
    for _ in range(ITERS):
        ts = time.strftime("%H:%M:%S")
        c, m = cpu_pct(), mem_pct()
        for t in TARGETS:
            ok, lat = check(t)
            total += 1
            up += 1 if ok else 0
            print("%s,%.1f,%.1f,%s,%s,%.1f" % (ts, c, m, t, "1" if ok else "0", lat))
        time.sleep(INTERVAL)
    disp = round(100 * up / total, 2) if total else 0
    print("# RESUMEN disponibilidad=%.2f%% muestras=%d objetivo>=99%%" % (disp, total))


if __name__ == "__main__":
    main()
