<#
.Synopsis
Create, populate and start Python venv.

.Description
This script creates a python virtual environment in the directory venv if non exists.
Then it installs all dependencies from requirements.in
The packages must be downloadable via pip or reside in the subdirectory packages.
If the requirements.in changes the update is performed accordingly.
#>

# $VerbosePreference = "Continue"

$global:x = $MyInvocation.line

<#
.Synopsis
Return if script was started by explorer click
#>
function IsNonInteractive
{
    return $global:x -like "*Get-ExecutionPolicy*"
}

$Errors = @()

$VenvExecPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$CURRENT_PATH = Get-Item -Path $VenvExecPath

$VENV_SCRIPT = Join-Path $CURRENT_PATH 'pyvenv.py'; Write-Verbose $VENV_SCRIPT
$VENV_PATH = Join-Path $CURRENT_PATH 'venv\'; Write-Verbose $VENV_PATH
$PYTHON_PATH = Join-Path $VENV_PATH 'Scripts\python.exe'; Write-Verbose $PYTHON_PATH
$PYTHON_ACTIVATE = Join-Path $VENV_PATH 'Scripts\Activate.ps1'; Write-Verbose $PYTHON_ACTIVATE

if (Get-Command "py.exe" -ErrorAction SilentlyContinue) {
    py.exe -3 $VENV_SCRIPT --min-version 3.6 --path $VENV_PATH;
} else {
   $Errors += "System Python executable not found"
}

If (-Not $?) {
    $Errors += "Script returned $LASTEXITCODE"
}

If (-Not (Test-Path -Path $PYTHON_ACTIVATE)) {
    $Errors += "Missing $PYTHON_ACTIVATE"
}

If ($Errors) {
    $Errors | ForEach { $Host.UI.WriteErrorLine("Error: $_") }
    If (IsNonInteractive) {
        pause
    }
    exit 1
}

If (IsNonInteractive) {
    invoke-expression "cmd /c start powershell -noexit $PYTHON_ACTIVATE"
} Else {
    . $PYTHON_ACTIVATE
}
