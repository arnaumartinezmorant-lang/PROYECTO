#!/usr/bin/env python3
"""Muestra que nodo (WEB01/WEB02) atiende cada peticion a traves del balanceador.
Uso: BASE_URL=http://127.0.0.1:18080 python3 whoami_sampler.py 8"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:18080")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
conteo = {}
for i in range(N):
    try:
        with urllib.request.urlopen(BASE + "/whoami", timeout=3) as r:
            node = json.loads(r.read()).get("node", "?")
            up = r.headers.get("X-Upstream", "-")
    except Exception as e:
        node, up = "ERROR(%s)" % e.__class__.__name__, "-"
    conteo[node] = conteo.get(node, 0) + 1
    print("  peticion %2d -> servida por %s (upstream %s)" % (i + 1, node, up))
print("  reparto:", ", ".join("%s=%d" % (k, v) for k, v in sorted(conteo.items())))
