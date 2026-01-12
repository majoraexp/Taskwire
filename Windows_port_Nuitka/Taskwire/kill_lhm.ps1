# Forcefully stop LibreHardwareMonitor to release file locks
$ProcessName = "LibreHardwareMonitor"

function Kill-LHM {
    $proc = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if (-not $proc) { return $true }

    Write-Host "Attempting to stop $ProcessName..."
    
    try {
        Stop-Process -Name $ProcessName -Force -ErrorAction Stop
        
        # Wait for it to die
        for ($i=0; $i -lt 5; $i++) {
            if (-not (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)) {
                Write-Host "Process stopped."
                return $true
            }
            Start-Sleep -Milliseconds 500
        }
    } catch {
        Write-Warning "Failed to stop process directly: $($_.Exception.Message)"
    }
    
    return $false
}

# 1. Try killing normally
if (Kill-LHM) {
    exit 0
}

# 2. If failed, check Admin status
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Process is likely running as Admin. Launching elevated killer..."
    
    # Run a simple kill command as Admin
    $killCommand = "Stop-Process -Name '$ProcessName' -Force -ErrorAction SilentlyContinue"
    $proc = Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$killCommand`"" -Verb RunAs -PassThru -WindowStyle Hidden
    
    # Wait for the elevated shell to finish
    $proc.WaitForExit()
    
    # Check one last time
    Start-Sleep -Seconds 1
    if (-not (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)) {
        Write-Host "Process stopped via Admin elevation."
        exit 0
    }
}

# 3. Final Failure
Write-Error "CRITICAL: Could not stop $ProcessName. Please close it manually via Task Manager before building."
exit 1
