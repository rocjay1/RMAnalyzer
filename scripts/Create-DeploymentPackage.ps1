# Description: Creates a deployment package for the AWS Lambda function

$location = Get-Location | Select-Object -ExpandProperty Path
if ($location -notlike "*\scripts") {
    Write-Error -Message "This script should be run from the scripts directory, 'cd' there and try again"
    exit
}

# Make sure the dist and packages directories exist
if (-not (Test-Path -Path "..\dist\packages\*")) {
    # Try to create the missing directories. If dist\packages is there but empty, silently continue.
    New-Item -Path "..\dist\packages" -ItemType Directory -ErrorAction SilentlyContinue | Out-Null
    # Manually add the yattag package
    Write-Error -Message "The yattag package has not been installed in the 'dist\packages' folder, run 'pip install yattag' there"
    exit
}

$compress = @{
    Path = '..\dist\packages\*', '..\lambda_function\src\main.py', '..\config\'
    CompressionLevel = 'Optimal'
    DestinationPath = '..\dist\pkg.zip'
}

Compress-Archive @compress -Force