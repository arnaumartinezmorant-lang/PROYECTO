<#
.SYNOPSIS
    Alta automatica de un nuevo empleado en Active Directory (CU-001 / US_01).
    Crea el usuario en la OU del departamento, lo mete en su grupo de seguridad,
    crea su carpeta personal y aplica permisos NTFS. Reemplaza el proceso manual
    de 5-10 min descrito en el shadowing por una sola ejecucion.

    Requiere el modulo ActiveDirectory (RSAT) y ejecutarse en un DC o equipo de gestion.
.EXAMPLE
    .\New-EmpleadoAD.ps1 -Nombre Ana -Apellidos Ruiz -Departamento Oficinas -Rol Oficina
#>
param(
    [Parameter(Mandatory)] [string]$Nombre,
    [Parameter(Mandatory)] [string]$Apellidos,
    [ValidateSet('Administracion','Soporte','Oficinas')] [string]$Departamento = 'Oficinas',
    [ValidateSet('Administracion','Tecnico','Oficina')]  [string]$Rol = 'Oficina',
    [string]$Dominio = 'corp.local'
)

$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory

$sam   = ($Nombre.Substring(0,1) + $Apellidos).ToLower() -replace '[^a-z0-9]', ''
$upn   = "$sam@$Dominio"
$ouMap = @{ Administracion='OU=Administracion'; Soporte='OU=Tecnicos'; Oficinas='OU=Oficinas' }
$ou    = "$($ouMap[$Departamento]),OU=Corp,DC=corp,DC=local"
$pass  = ConvertTo-SecureString -AsPlainText 'Cambiar123!' -Force

Write-Host "[AD] Creando usuario $sam en $ou ..."
New-ADUser -Name "$Nombre $Apellidos" -GivenName $Nombre -Surname $Apellidos `
    -SamAccountName $sam -UserPrincipalName $upn -Path $ou `
    -AccountPassword $pass -ChangePasswordAtLogon $true -Enabled $true `
    -EmailAddress $upn

# Grupo de seguridad por rol (GG_Tecnicos, GG_Administracion, GG_Oficina)
$grupo = "GG_$Rol"
Add-ADGroupMember -Identity $grupo -Members $sam
Write-Host "[AD] $sam anadido al grupo $grupo"

# Carpeta personal + permisos NTFS
$home = "\\BKP01\Perfiles$\$sam"
New-Item -ItemType Directory -Path $home -Force | Out-Null
$acl = Get-Acl $home
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "$Dominio\$sam","Modify","ContainerInherit,ObjectInherit","None","Allow")
$acl.AddAccessRule($rule); Set-Acl $home $acl
Write-Host "[AD] Carpeta personal y permisos NTFS aplicados en $home"
Write-Host "[AD] Alta completada para $upn (rol $Rol, dpto $Departamento)"
