# Workspace Migration Package

Toolkit completo para migrar escritorios VDI a Huawei Cloud Workspace usando la estrategia re-deploy (reconstruir desde cero en el destino y migrar datos del usuario).

Incluye 3 skills para agentes IA (Hermes, Claude Code, OpenCode, Codex), scripts de PowerShell y Python listos para usar, y una guia de migracion paso a paso.

---

## Que hacen estas skills y por que son utiles

### El problema

Cuando migras un escritorio VDI a la nube, necesitas reinstalar todo el software que tenia el usuario. Pero:

- No tienes una lista completa de que estaba instalado (y no te puedes fiar de lo que el usuario recuerde)
- Los instaladores originales (.msi) estan enterrados en `C:\Windows\Installer\` con nombres aleatorios como `22ca53.msi` -- no hay forma humana de saber cual es cual
- Instalar 50+ paquetes a mano uno por uno es inviable
- Necesitas verificar que el destino quedo identico al origen

### La solucion: 3 skills que cubren el flujo completo

```
  INVENTARIAR          RESPALDAR            INSTALAR            VERIFICAR
  (que hay?)           (los .msi)           (en el destino)     (quedo igual?)
      |                    |                    |                    |
      v                    v                    v                    v
  Skill 1             Skill 2              Skill 3              Skill 1
  software-inv        msi-inventory        msi-batch-installer  software-inv
```

#### Skill 1: windows-software-inventory

**Para que sirve:** Escanea un sistema Windows y lista TODO el software instalado -- nombre, version, publisher, fecha de instalacion, comando de desinstalacion. No se le escapa nada porque consulta las 4 claves del registro donde Windows registra aplicaciones (HKLM + HKCU, 64-bit + 32-bit).

**Por que es mejor que otros metodos:**
- `Win32_Product` (WMI) es lentisimo (10-60s) y ademas peligroso -- puede reconfigurar paquetes MSI durante el escaneo. Microsoft mismo lo advierte.
- Mirar "Agregar o quitar programas" a mano es lento e incompleto (no muestra apps per-user, no muestra 32-bit en sistemas 64-bit).
- Esta skill usa el registro directamente: instantaneo, completo, seguro.

**Que produce:** Un CSV y JSON con todas las aplicaciones, listo para clasificar y comparar.

#### Skill 2: windows-msi-inventory

**Para que sirve:** Encuentra los instaladores .msi que Windows tiene cacheados en `C:\Windows\Installer\` (con nombres hex aleatorios), los mapea al software que corresponden via el registro, lee sus propiedades (ProductCode, UpgradeCode, Manufacturer), y los respalda con nombres legibles.

**Por que es necesario:**
- No puedes simplemente copiar `C:\Windows\Installer\*.msi` porque no sabes que es cada archivo.
- Algunos .msi originales pueden seguir en el directorio de descarga (`InstallSource`) con su nombre real -- la skill los busca tambien.
- Sin este respaldo, tendrias que descargar cada instalador de nuevo desde la web del vendor.

**Que produce:** Una carpeta con todos los .msi de terceros renombrados legiblemente (ej: `7_Zip_26_01_x64.msi`), mas un CSV con el manifiesto.

#### Skill 3: msi-batch-installer

**Para que sirve:** Instala un lote de .msi en silencio (sin interaccion del usuario) usando `msiexec`, con logging completo, decodificacion de codigos de error, y un reporte de pass/fail al final.

**Por que es mejor que instalar a mano:**
- Instala 50 paquetes en minutos vs horas a mano.
- Cada instalacion genera un log verbose en `%TEMP%\msi-install-logs\` para debug.
- Decodifica codigos de error (1603 = permisos, 1618 = otra instalacion en curso, 3010 = necesita reboot).
- Continua con el siguiente paquete si uno falla (configurable).
- Provee scripts CMD y PowerShell con helpers de elevacion.

**Que produce:** Todo el software instalado en el destino + reporte de exito/fallo por paquete.

---

## Que incluye este paquete

```
workspace-migration/
|
|-- skills/                          Las 3 skills (SKILL.md + scripts)
|   |-- windows-software-inventory/
|   |   |-- SKILL.md
|   |   +-- scripts/scan_software.py
|   |-- windows-msi-inventory/
|   |   |-- SKILL.md
|   |   +-- scripts/scan_msi_installers.py
|   +-- msi-batch-installer/
|       |-- SKILL.md
|       +-- scripts/install-msi.ps1, install-msi.cmd
|
|-- msi-installer/                   Flujo estructurado de instalacion
|   |-- scripts/
|   |   |-- 00_env_check.ps1         Verifica prerequisitos
|   |   |-- 01_discover_msi.ps1      Descubre .msi en el directorio
|   |   |-- 02_install_msi.ps1       Instala en batch
|   |   +-- 03_verify_install.ps1    Verifica que todo quedo instalado
|   |-- lib/
|   |   |-- msi_utils.ps1            Funciones de utilidad MSI
|   |   +-- report_utils.ps1         Funciones de reporte JSON
|   |-- configs/
|   |   +-- install.yaml             Config (UI mode, props, log dir)
|   +-- examples/
|       |-- run-elevated.ps1         Helper para elevar a Admin
|       +-- run-elevated-cmd.ps1     Helper para elevar (CMD)
|
|-- VDI-to-Huawei-Cloud-Workspace-Migration-Guide.md   Guia completa 8 fases
+-- README.md                        (este archivo)
```

---

## Instalacion

Las skills son documentos markdown (SKILL.md) con frontmatter YAML + instrucciones. Cada agente IA las carga desde su propia ruta. Los scripts acompanan a cada skill en su directorio.

### Opcion A: Hermes Agent

Hermes carga skills desde `~/.hermes/skills/<categoria>/<nombre>/`. Las skills ya estan instaladas ahi (paquete instalado el 2026-07-22). Si necesitas reinstalar:

```bash
# Copiar las 3 skills al directorio de Hermes
cp -r skills/software-development/windows-software-inventory ~/.hermes/skills/software-development/
cp -r skills/software-development/windows-msi-inventory      ~/.hermes/skills/software-development/
cp -r skills/software-development/msi-batch-installer        ~/.hermes/skills/software-development/

# Verificar que estan disponibles
hermes skills list | grep -E 'windows|msi'

# Cargar una skill en la sesion actual
/skill windows-software-inventory
```

### Opcion B: Claude Code

Claude Code lee archivos `CLAUDE.md` o `AGENTS.md` del directorio de trabajo. Para usar estas skills:

```bash
# Copiar los SKILL.md al directorio del proyecto
mkdir -p ~/.claude/skills
cp skills/software-development/windows-software-inventory/SKILL.md ~/.claude/skills/windows-software-inventory.md
cp skills/software-development/windows-msi-inventory/SKILL.md      ~/.claude/skills/windows-msi-inventory.md
cp skills/software-development/msi-batch-installer/SKILL.md        ~/.claude/skills/msi-batch-installer.md

# O poner un AGENTS.md en el proyecto que referencie las skills
echo "See skills/ directory for migration procedures." > AGENTS.md
```

Los scripts (scan_software.py, scan_msi_installers.py, install-msi.ps1) se usan directamente desde el directorio del proyecto -- el agente los ejecuta con `python` o `powershell`.

### Opcion C: OpenCode

OpenCode usa `AGENTS.md` y carga skills desde su directorio de configuracion:

```bash
# Copiar skills
mkdir -p ~/.opencode/skills
cp -r skills/software-development/windows-software-inventory ~/.opencode/skills/
cp -r skills/software-development/windows-msi-inventory      ~/.opencode/skills/
cp -r skills/software-development/msi-batch-installer        ~/.opencode/skills/
```

### Opcion D: OpenAI Codex

Codex CLI lee `AGENTS.md` del repo. Copiar el proyecto y los scripts al directorio de trabajo:

```bash
# Codex ejecuta comandos del directorio -- solo necesita acceso a los scripts
cp -r workspace-migration /path/to/project/
cd /path/to/project/workspace-migration
# Codex leera AGENTS.md y podra ejecutar los scripts directamente
```

### Opcion E: Cualquier agente (uso generico)

Las skills son solo documentacion + scripts. Puedes usarlas sin ningun agente:

```powershell
# Fase 1: Inventariar
python scripts/scan_software.py --full --json inventory.json --csv inventory.csv

# Fase 2: Respaldar MSI
python scripts/scan_msi_installers.py --backup "C:\Backup\msi" --props

# Fase 5: Instalar
powershell -File msi-installer/scripts/02_install_msi.ps1
```

---

## Como usar las skills con un agente IA

### Desencadenantes naturales (que decirle al agente)

El agente cargara la skill apropiada automaticamente cuando detecte intencion. Estos son los prompts que activan cada skill:

#### Para inventariar software (Skill 1)

```
"Escanear el VDI origen para listar todo el software instalado"
"Hacer un inventario completo de programas en esta maquina Windows"
"Que software tiene instalado este equipo? Exporta a CSV"
"Comparar el software del VDI origen vs el destino"
```

#### Para respaldar instaladores MSI (Skill 2)

```
"Encontrar y respaldar todos los instaladores MSI de terceros"
"Extraer los .msi cacheados en C:\Windows\Installer con sus nombres reales"
"Back up de los instaladores MSI para la migracion"
"Leer las propiedades (ProductCode, UpgradeCode) de los MSI instalados"
```

#### Para instalar en batch (Skill 3)

```
"Instalar todos los .msi del directorio de staging silenciosamente"
"Ejecutar el flujo completo de instalacion MSI en el destino"
"Instalar los paquetes MSI en batch con logging"
"Correr el flujo: env check, discover, install, verify"
```

#### Para la migracion completa

```
"Ejecutar la migracion VDI to Huawei Cloud completa"
"Seguir la guia de migracion paso a paso"
"Hacer el re-deploy: inventariar, respaldar, instalar, verificar"
```

### Flujo estructurado (scripts en orden)

Si prefieres ejecutar el flujo paso a paso con los scripts estructurados:

```powershell
# 0. Verificar entorno (admin, msiexec, config, espacio)
.\msi-installer\scripts\00_env_check.ps1

# 1. Descubrir .msi en el directorio de staging
$env:MSI_DIR = "\\staging-server\migration\msi-backup"
.\msi-installer\scripts\01_discover_msi.ps1

# 2. Instalar (requiere aprobacion: crear archivo vacio)
mkdir approvals; touch approvals\APPROVED_INSTALL
.\msi-installer\scripts\02_install_msi.ps1

# 3. Verificar instalacion
.\msi-installer\scripts\03_verify_install.ps1
```

Cada paso genera un reporte JSON en `msi-installer/reports/`.

---

## Flujo de migracion (resumen)

La guia completa esta en `VDI-to-Huawei-Cloud-Workspace-Migration-Guide.md` (8 fases). Resumen:

```
Fase 1: INVENTARIAR    Escanear VDI origen          -> source_inventory.csv
         |              Skill: windows-software-inventory
         v
Fase 2: RESPALDAR      Extraer .msi cacheados        -> msi-backup/
         |              Skill: windows-msi-inventory
         v
Fase 3: EMPAQUETAR      Organizar en staging share    -> staging/
         |
         v
Fase 4: PREPARAR        Provisionar destino limpio    -> Huawei Cloud desktop
         |
         v
Fase 5: INSTALAR        Instalar .msi en batch        -> install logs
         |              Skill: msi-batch-installer
         v
Fase 6: MIGRAR DATOS    Copiar perfiles y archivos    -> user-data/
         |
         v
Fase 7: VERIFICAR       Comparar origen vs destino    -> parity report
         |              Skill: windows-software-inventory
         v
Fase 8: CORTOVER        UAT, sign-off, decomisionar
```

---

## Scripts de referencia rapida

### scan_software.py (Skill 1)

```bash
python scan_software.py --full --json out.json --csv out.csv   # Inventario completo
python scan_software.py --search "Python"                       # Buscar especifico
python scan_software.py --full                                   # Incluye Store + Chocolatey
```

### scan_msi_installers.py (Skill 2)

```bash
python scan_msi_installers.py --props                            # Listar MSI + propiedades
python scan_msi_installers.py --backup "C:\Backup"              # Respaldar .msi
python scan_msi_installers.py --extract "C:\Extracted"          # Extraer contenidos
python scan_msi_installers.py --all                              # Incluir Microsoft products
```

### install-msi.ps1 (Skill 3)

```powershell
.\install-msi.ps1 -Path "C:\Packages"                           # Instalar todo en dir
.\install-msi.ps1 -Path "app1.msi","app2.msi"                   # Instalar especificos
.\install-msi.ps1 -Path "C:\Packages" -UiMode basic             # Con progress bar
.\install-msi.ps1 -Path "C:\Packages" -ContinueOnError:$false   # Parar en primer error
```

---

## Requisitos

| Componente | Requisito |
|------------|-----------|
| VDI origen | Windows 10/11, PowerShell 3.0+, Python 3.11+, acceso Admin |
| Destino | Huawei Cloud Workspace (Windows) |
| Staging | SMB share accesible desde origen y destino |
| Agente IA | Hermes / Claude Code / OpenCode / Codex (opcional) |

---

## Codigos de error comunes de msiexec

| Codigo | Significado | Accion |
|--------|-------------|--------|
| 0 | Exito | -- |
| 1602 | Usuario cancelo | Revisar UI mode |
| 1603 | Error fatal | Permisos o archivos bloqueados -- correr como Admin |
| 1618 | Otra instalacion en curso | Esperar y reintentar |
| 1619 | MSI no abre | Archivo faltante o corrupto |
| 1638 | Otra version ya instalada | Desinstalar version existente primero |
| 3010 | Exito pero necesita reboot | Reiniciar y continuar |

---

*Version: 1.0 -- Julio 2026*
*Skills: windows-software-inventory, windows-msi-inventory, msi-batch-installer*
*Estrategia: Re-deploy (rebuild + migracion de datos)*
*Destino: Huawei Cloud Workspace*
