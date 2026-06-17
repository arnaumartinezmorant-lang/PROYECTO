#!/usr/bin/env bash
# Monitorizacion de espacio en disco con alerta temprana (tarea 5 de automatizacion).
# Lanza una alerta si el uso supera el umbral. Equivalente a Get-Volume (PowerShell).
set -euo pipefail
UMBRAL="${1:-85}"   # porcentaje
echo "[disk] $(date '+%F %T') umbral de alerta = ${UMBRAL}%"
df -hP | awk -v u="$UMBRAL" 'NR>1 {
    gsub("%","",$5);
    estado = ($5+0 >= u) ? "ALERTA" : "OK";
    printf "  %-8s uso=%3s%% mont=%s -> %s\n", estado, $5, $6, estado
}'
