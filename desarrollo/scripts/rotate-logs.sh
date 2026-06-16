#!/usr/bin/env bash
# Rotacion y limpieza de logs (tarea 4 de automatizacion).
# Comprime logs y elimina los anteriores a N dias.
set -euo pipefail
LOGDIR="${1:-$(dirname "$0")/../evidencias/logs}"
DIAS="${2:-90}"
mkdir -p "$LOGDIR"
echo "[logrotate] comprimiendo logs en $LOGDIR"
find "$LOGDIR" -maxdepth 1 -name '*.log' -mmin +0 -exec gzip -f {} \; 2>/dev/null || true
echo "[logrotate] eliminando comprimidos de mas de ${DIAS} dias"
find "$LOGDIR" -name '*.log.gz' -type f -mtime +"$DIAS" -delete 2>/dev/null || true
echo "[logrotate] hecho. Contenido actual:"
ls -la "$LOGDIR" 2>/dev/null || true
