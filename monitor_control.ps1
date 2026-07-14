param(
    [ValidateSet('menu', 'list', 'set')]
    [string]$Action = 'menu',
    [string]$Device = '',
    [ValidateSet('on', 'off')]
    [string]$State = ''
)

$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class CfgHelper
{
    [StructLayout(LayoutKind.Sequential)]
    public struct LUID { public uint LowPart; public int HighPart; }

    [StructLayout(LayoutKind.Sequential)]
    public struct DISPLAYCONFIG_RATIONAL { public uint Numerator; public uint Denominator; }

    [StructLayout(LayoutKind.Sequential)]
    public struct DISPLAYCONFIG_PATH_SOURCE_INFO
    {
        public LUID adapterId;
        public uint id;
        public uint modeInfoIdx;
        public uint statusFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct DISPLAYCONFIG_PATH_TARGET_INFO
    {
        public LUID adapterId;
        public uint id;
        public uint modeInfoIdx;
        public uint outputTechnology;
        public uint rotation;
        public uint scaling;
        public DISPLAYCONFIG_RATIONAL refreshRate;
        public uint scanLineOrdering;
        public bool targetAvailable;
        public uint statusFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct DISPLAYCONFIG_PATH_INFO
    {
        public DISPLAYCONFIG_PATH_SOURCE_INFO sourceInfo;
        public DISPLAYCONFIG_PATH_TARGET_INFO targetInfo;
        public uint flags;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct DISPLAYCONFIG_MODE_INFO
    {
        public uint infoType;
        public uint id;
        public LUID adapterId;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 48)]
        public byte[] modeUnion;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct DISPLAYCONFIG_DEVICE_INFO_HEADER
    {
        public uint type;
        public uint size;
        public LUID adapterId;
        public uint id;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct DISPLAYCONFIG_SOURCE_DEVICE_NAME
    {
        public DISPLAYCONFIG_DEVICE_INFO_HEADER header;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string viewGdiDeviceName;
    }

    public const uint QDC_ALL_PATHS = 0x00000001;
    public const uint DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1;
    public const uint DISPLAYCONFIG_PATH_ACTIVE = 0x00000001;
    public const uint MODE_IDX_INVALID = 0xFFFFFFFF;

    public const uint SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x00000020;
    public const uint SDC_APPLY = 0x00000080;
    public const uint SDC_SAVE_TO_DATABASE = 0x00000200;
    public const uint SDC_ALLOW_CHANGES = 0x00000400;
    public const uint SDC_FORCE_MODE_ENUMERATION = 0x00001000;

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetDisplayConfigBufferSizes(uint flags, out uint numPathArrayElements, out uint numModeInfoArrayElements);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int QueryDisplayConfig(uint flags, ref uint numPathArrayElements, [In, Out] DISPLAYCONFIG_PATH_INFO[] pathArray, ref uint numModeInfoArrayElements, [In, Out] DISPLAYCONFIG_MODE_INFO[] modeInfoArray, IntPtr currentTopologyId);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int SetDisplayConfig(uint numPathArrayElements, [In] DISPLAYCONFIG_PATH_INFO[] pathArray, uint numModeInfoArrayElements, [In] DISPLAYCONFIG_MODE_INFO[] modeInfoArray, uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int DisplayConfigGetDeviceInfo(ref DISPLAYCONFIG_SOURCE_DEVICE_NAME deviceName);
}
"@

function Get-Topology {
    $pathCount = 0
    $modeCount = 0
    $rc = [CfgHelper]::GetDisplayConfigBufferSizes([CfgHelper]::QDC_ALL_PATHS, [ref]$pathCount, [ref]$modeCount)
    if ($rc -ne 0) { throw "GetDisplayConfigBufferSizes falhou (codigo $rc)" }

    $paths = New-Object 'CfgHelper+DISPLAYCONFIG_PATH_INFO[]' $pathCount
    $modes = New-Object 'CfgHelper+DISPLAYCONFIG_MODE_INFO[]' $modeCount
    $rc = [CfgHelper]::QueryDisplayConfig([CfgHelper]::QDC_ALL_PATHS, [ref]$pathCount, $paths, [ref]$modeCount, $modes, [IntPtr]::Zero)
    if ($rc -ne 0) { throw "QueryDisplayConfig falhou (codigo $rc)" }

    if ($paths.Length -ne $pathCount) { $paths = $paths[0..($pathCount - 1)] }
    if ($modes.Length -ne $modeCount) { $modes = $modes[0..($modeCount - 1)] }

    return @{ Paths = $paths; Modes = $modes }
}

function Get-GdiName($sourceInfo) {
    $devName = New-Object CfgHelper+DISPLAYCONFIG_SOURCE_DEVICE_NAME
    $devName.header.type = [CfgHelper]::DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
    $devName.header.size = [System.Runtime.InteropServices.Marshal]::SizeOf($devName)
    $devName.header.adapterId = $sourceInfo.adapterId
    $devName.header.id = $sourceInfo.id
    $rc = [CfgHelper]::DisplayConfigGetDeviceInfo([ref]$devName)
    if ($rc -eq 0 -and $devName.viewGdiDeviceName) {
        return $devName.viewGdiDeviceName
    }
    return "\\.\DISPLAY$($sourceInfo.id + 1)"
}

function Get-MonitorGroups {
    $topo = Get-Topology
    $paths = $topo.Paths

    $groups = @{}
    for ($i = 0; $i -lt $paths.Length; $i++) {
        $p = $paths[$i]
        if (-not $p.targetInfo.targetAvailable) { continue }
        $key = $p.targetInfo.id
        $active = ($p.flags -band [CfgHelper]::DISPLAYCONFIG_PATH_ACTIVE) -ne 0
        if (-not $groups.ContainsKey($key)) { $groups[$key] = @() }
        $groups[$key] += [PSCustomObject]@{ Index = $i; SourceId = $p.sourceInfo.id; Active = $active }
    }

    $result = @()
    foreach ($key in $groups.Keys) {
        $entries = $groups[$key]
        $activeEntry = $entries | Where-Object { $_.Active } | Select-Object -First 1
        $chosen = if ($activeEntry) { $activeEntry } else { $entries | Select-Object -First 1 }
        $chosenPath = $paths[$chosen.Index]
        $gdiName = Get-GdiName $chosenPath.sourceInfo

        $result += [PSCustomObject]@{
            TargetId    = $key
            ActiveIndex = if ($activeEntry) { $activeEntry.Index } else { $null }
            Entries     = $entries
            Active      = [bool]$activeEntry
            GdiName     = $gdiName
        }
    }
    return @{ Groups = $result; Paths = $paths; Modes = $topo.Modes }
}

function Set-PathActive($topo, $pathIndex, $active) {
    $paths = $topo.Paths

    if ($active) {
        $paths[$pathIndex].flags = $paths[$pathIndex].flags -bor [CfgHelper]::DISPLAYCONFIG_PATH_ACTIVE
    } else {
        $paths[$pathIndex].flags = $paths[$pathIndex].flags -band (-bnot [CfgHelper]::DISPLAYCONFIG_PATH_ACTIVE)
    }
    # Invalida os indices de modo desse path para forcar o Windows a
    # recalcular/atribuir modos validos em vez de reaproveitar indices
    # que podem ficar inconsistentes com a nova flag (causava "meio ligado").
    $paths[$pathIndex].sourceInfo.modeInfoIdx = [CfgHelper]::MODE_IDX_INVALID
    $paths[$pathIndex].targetInfo.modeInfoIdx = [CfgHelper]::MODE_IDX_INVALID

    $flags = [CfgHelper]::SDC_APPLY -bor [CfgHelper]::SDC_USE_SUPPLIED_DISPLAY_CONFIG -bor [CfgHelper]::SDC_ALLOW_CHANGES -bor [CfgHelper]::SDC_SAVE_TO_DATABASE -bor [CfgHelper]::SDC_FORCE_MODE_ENUMERATION
    $rc = [CfgHelper]::SetDisplayConfig([uint32]$paths.Length, $paths, [uint32]$topo.Modes.Length, $topo.Modes, $flags)
    return $rc
}

function Set-MonitorActive($gdiName, $active) {
    $data = Get-MonitorGroups
    $sel = $data.Groups | Where-Object { $_.GdiName -eq $gdiName } | Select-Object -First 1
    if (-not $sel) {
        return @{ ok = $false; error = "monitor '$gdiName' nao encontrado" }
    }
    if ($active) {
        $target = $sel.Entries | Select-Object -First 1
        $rc = Set-PathActive $data $target.Index $true
    } else {
        if (-not $sel.Active) {
            return @{ ok = $true; rc = 0; note = 'ja estava desativado' }
        }
        $rc = Set-PathActive $data $sel.ActiveIndex $false
    }
    return @{ ok = ($rc -eq 0); rc = $rc }
}

# ── Modo nao interativo (usado pelo servidor remote-control) ────────────────
if ($Action -eq 'list') {
    $data = Get-MonitorGroups
    $data.Groups | Select-Object GdiName, Active | ConvertTo-Json | Write-Output
    exit
}

if ($Action -eq 'set') {
    if (-not $Device -or -not $State) {
        Write-Output (@{ ok = $false; error = 'parametros -Device e -State sao obrigatorios' } | ConvertTo-Json)
        exit 1
    }
    $result = Set-MonitorActive $Device ($State -eq 'on')
    Write-Output ($result | ConvertTo-Json)
    exit
}

# ── Modo interativo (uso manual, clique duplo) ──────────────────────────────
Write-Host "Lendo configuracao atual dos monitores..."
$data = Get-MonitorGroups
$groups = $data.Groups

if (-not $groups -or $groups.Count -eq 0) {
    Write-Host "Nenhum monitor encontrado."
    Read-Host "Pressione Enter para sair"
    exit
}

Write-Host ""
Write-Host "=== Monitores detectados ==="
for ($i = 0; $i -lt $groups.Count; $i++) {
    $g = $groups[$i]
    $status = if ($g.Active) { "ATIVO" } else { "DESATIVADO" }
    Write-Host "$($i + 1). $($g.GdiName) - $status"
}
Write-Host ""

$escolha = Read-Host "Digite o numero do monitor que deseja ativar/desativar"
$indice = 0
if (-not [int]::TryParse($escolha, [ref]$indice) -or $indice -lt 1 -or $indice -gt $groups.Count) {
    Write-Host "Opcao invalida."
    Read-Host "Pressione Enter para sair"
    exit
}

$sel = $groups[$indice - 1]
$result = Set-MonitorActive $sel.GdiName (-not $sel.Active)

if ($result.ok) {
    Write-Host "Feito."
} else {
    Write-Host "Falhou: $($result.error) $($result.rc)"
    Write-Host "(rc 0 = sucesso; qualquer outro numero indica que o Windows recusou a mudanca)"
}

Read-Host "Pressione Enter para fechar"
