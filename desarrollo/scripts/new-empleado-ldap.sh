#!/usr/bin/env bash
# =============================================================================
# Alta automatica de un nuevo empleado en el directorio FreeIPA (CU-001 / US_01).
# Crea el usuario, lo mete en su grupo (segun departamento/rol), crea su carpeta
# personal en el servidor de ficheros y aplica permisos POSIX/ACL. Reemplaza el
# proceso manual de 5-10 min descrito en el shadowing por una sola ejecucion.
#
# Equivalente Linux del antiguo New-EmpleadoAD.ps1 (PowerShell/Active Directory).
# Requiere: cliente FreeIPA (ipa) autenticado con un ticket Kerberos de admin
#   (kinit admin) y permisos para crear usuarios.
#
# Uso: ./new-empleado-ldap.sh -n Ana -a Ruiz -d Oficinas -r oficina
# =============================================================================
set -euo pipefail

NOMBRE=""; APELLIDOS=""; DEPARTAMENTO="Oficinas"; ROL="oficina"; DOMINIO="corp.local"
while getopts "n:a:d:r:" opt; do
  case "$opt" in
    n) NOMBRE="$OPTARG" ;;
    a) APELLIDOS="$OPTARG" ;;
    d) DEPARTAMENTO="$OPTARG" ;;
    r) ROL="$OPTARG" ;;
    *) echo "Uso: $0 -n Nombre -a Apellidos -d Departamento -r rol"; exit 1 ;;
  esac
done
[ -z "$NOMBRE" ] || [ -z "$APELLIDOS" ] && { echo "Faltan -n y -a"; exit 1; }

# login = inicial + apellido en minusculas, sin caracteres raros
LOGIN=$(echo "${NOMBRE:0:1}${APELLIDOS}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')
GRUPO="gg_${ROL}"            # gg_tecnico / gg_administracion / gg_oficina
HOME_DIR="/srv/perfiles/${LOGIN}"

echo "[FreeIPA] creando usuario ${LOGIN} (${NOMBRE} ${APELLIDOS}) en ${DOMINIO}"
ipa user-add "$LOGIN" --first="$NOMBRE" --last="$APELLIDOS" \
    --email="${LOGIN}@${DOMINIO}" --homedir="$HOME_DIR" \
    --random | grep -i "contrase\|password" || true

echo "[FreeIPA] anadiendo ${LOGIN} al grupo ${GRUPO}"
ipa group-add-member "$GRUPO" --users="$LOGIN"

echo "[FS] creando carpeta personal y permisos POSIX/ACL en ${HOME_DIR}"
install -d -m 0700 -o "$LOGIN" "$HOME_DIR" 2>/dev/null || sudo install -d -m 0700 "$HOME_DIR"
# ACL: solo el usuario y el grupo de tecnicos pueden entrar
setfacl -m u:"$LOGIN":rwx -m g:gg_tecnico:r-x "$HOME_DIR" 2>/dev/null || \
  echo "  (setfacl requiere privilegios; aplicar en el servidor de ficheros)"

echo "[OK] alta completada para ${LOGIN}@${DOMINIO} (rol ${ROL}, dpto ${DEPARTAMENTO})"
