#!/usr/bin/env bash
# Restauracion de una copia cifrada (prueba de recuperacion - RTO).
# Uso: ./restore.sh <fichero.enc> <ruta_db_destino>
set -euo pipefail

ENC="${1:?Indica el fichero .enc a restaurar}"
DEST_DB="${2:-/tmp/intranet_restaurada.db}"
PASSPHRASE="${BACKUP_PASSPHRASE:-BackupLab2025!}"

START=$(date +%s)
echo "[restore] descifrando $ENC"
TMP="/tmp/restore_$$.bak"
gpg --batch --yes --pinentry-mode loopback --passphrase "$PASSPHRASE" \
    -d -o "$TMP" "$ENC" 2>/dev/null || true
if [ ! -s "$TMP" ]; then echo "[restore] ERROR: descifrado fallido"; exit 1; fi

cp "$TMP" "$DEST_DB"
# Verificacion de integridad
INTEG=$(sqlite3 "$DEST_DB" "PRAGMA integrity_check;")
N=$(sqlite3 "$DEST_DB" "SELECT count(*) FROM usuario;")
END=$(date +%s)
rm -f "$TMP"

echo "[restore] base restaurada en $DEST_DB"
echo "[restore] integrity_check = $INTEG"
echo "[restore] usuarios recuperados = $N"
echo "[restore] RTO medido = $((END-START)) s"
