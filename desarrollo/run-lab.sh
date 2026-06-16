#!/usr/bin/env bash
# =============================================================================
# Arranca el laboratorio reproducible SIN Docker (solo Python + utilidades del
# sistema), ejecuta todas las pruebas y genera las EVIDENCIAS en evidencias/.
# Es la version que permite demostrar el proyecto en cualquier maquina.
# (La version con contenedores esta en docker-compose.yml.)
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
EV="$ROOT/evidencias"
mkdir -p "$EV/logs" "$EV/salidas" "$EV/backups"
export DB_PATH="$ROOT/app/data/intranet.db"
rm -f "$DB_PATH"

# Puertos (altos para evitar conflictos con servicios del sistema)
P1=18001; P2=18002; PLB=18080
LBURL="http://127.0.0.1:${PLB}"
CURL="curl -s --noproxy 127.0.0.1,localhost"

echo "### 0. Entorno"
python3 --version; sqlite3 --version | awk '{print "sqlite "$1}'; gpg --version | head -1

echo "### 0b. Limpiar procesos huerfanos de ejecuciones previas"
pkill -f 'desarrollo/app/app.py' 2>/dev/null || true
pkill -f 'desarrollo/lb/balanceador.py' 2>/dev/null || true
sleep 1

echo "### 1. Sembrar base de datos"
( cd app && python3 seed.py ) | tee "$EV/salidas/01-seed.txt"

echo "### 2. Arrancar nodos WEB01 (:$P1) y WEB02 (:$P2) y el balanceador (:$PLB)"
APP_NODE=WEB01 PORT=$P1 python3 -u app/app.py > "$EV/logs/web01.log" 2>&1 &
W1=$!
APP_NODE=WEB02 PORT=$P2 python3 -u app/app.py > "$EV/logs/web02.log" 2>&1 &
W2=$!
BACKENDS="127.0.0.1:$P1,127.0.0.1:$P2" PORT=$PLB python3 -u lb/balanceador.py > "$EV/logs/lb.log" 2>&1 &
LB=$!
trap 'kill $W1 $W2 $LB 2>/dev/null' EXIT
sleep 2
# Esperar a que el balanceador sirva correctamente antes de medir (warm-up)
for i in $(seq 1 15); do
  if NO_PROXY="127.0.0.1,localhost" python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('$LBURL/whoami',timeout=2).status==200 else 1)" 2>/dev/null; then
    echo "Balanceador listo tras ${i}s"; break
  fi
  sleep 1
done

echo "### 3. Comprobacion de salud y reparto de carga (whoami x6)"
{
  echo "== LB health =="; $CURL "$LBURL/lb-health"
  echo "== whoami x6 (debe alternar WEB01/WEB02) =="
  NO_PROXY="127.0.0.1,localhost" BASE_URL="$LBURL" python3 pruebas/whoami_sampler.py 6
} | tee "$EV/salidas/02-balanceo.txt"

echo "### 4. Plan de pruebas de caja negra"
NO_PROXY="127.0.0.1,localhost" BASE_URL="$LBURL" python3 pruebas/run_tests.py | tee "$EV/salidas/03-pruebas-caja-negra.txt"
TEST_RC=${PIPESTATUS[0]}

echo "### 5. Prueba de FAILOVER (alta disponibilidad)"
{
  echo "Estado inicial: ambos nodos arriba"
  NO_PROXY="127.0.0.1,localhost" BASE_URL="$LBURL" python3 pruebas/whoami_sampler.py 4
  echo ">> Apagamos WEB01 (kill $W1) ..."
  kill "$W1" 2>/dev/null
  sleep 3
  echo "Tras la caida de WEB01, el servicio SIGUE (debe responder solo WEB02):"
  NO_PROXY="127.0.0.1,localhost" BASE_URL="$LBURL" python3 pruebas/whoami_sampler.py 4
  echo ">> Rearrancamos WEB01 ..."
  APP_NODE=WEB01 PORT=$P1 python3 -u app/app.py > "$EV/logs/web01.log" 2>&1 &
  W1=$!
  sleep 4
  echo "WEB01 recuperado, vuelve a repartirse la carga:"
  NO_PROXY="127.0.0.1,localhost" BASE_URL="$LBURL" python3 pruebas/whoami_sampler.py 6
} | tee "$EV/salidas/04-failover.txt"

echo "### 6. Copia de seguridad 3-2-1 cifrada + restauracion"
bash scripts/backup.sh "$DB_PATH" "$EV/backups" | tee "$EV/salidas/05-backup.txt"
ENC=$(ls -1t "$EV/backups/local/"*.enc | head -1)
bash scripts/restore.sh "$ENC" /tmp/intranet_restaurada.db | tee "$EV/salidas/06-restore.txt"

echo "### 7. Informes de explotacion (SQL de negocio)"
sqlite3 -header -column "$DB_PATH" < observabilidad/informes-sql.sql | tee "$EV/salidas/07-informes-sql.txt"
echo "-- comprobacion de cifrado en reposo: el .enc no debe contener texto plano --" | tee -a "$EV/salidas/07-informes-sql.txt"
( strings "$ENC" | grep -i "corp.local" && echo "FALLO: texto en claro" || echo "OK: no se encuentra texto en claro en el backup cifrado" ) | tee -a "$EV/salidas/07-informes-sql.txt"

echo "### 8. Monitorizacion (metricas y disponibilidad)"
ITERS=5 TARGETS="$LBURL/lb-health,http://127.0.0.1:$P1/health,http://127.0.0.1:$P2/health" \
  NO_PROXY="127.0.0.1,localhost" python3 monitor/monitor.py | tee "$EV/salidas/08-monitor.txt"

echo "### 9. Monitorizacion de disco"
bash scripts/disk-monitor.sh 85 | tee "$EV/salidas/09-disco.txt"

echo
echo "==================================================="
echo " Laboratorio ejecutado. Evidencias en: evidencias/"
echo " Resultado de las pruebas de caja negra: RC=$TEST_RC"
echo "==================================================="
exit $TEST_RC
