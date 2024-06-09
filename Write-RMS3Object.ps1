[CmdletBinding()]
param (
    $DirectoryPath = '/Users/roccodavino/Downloads',
    $BucketName = 'rm-analyzer-sheets-prd'
)

Import-Module AWS.Tools.S3

$file = Get-ChildItem -Path $DirectoryPath -Filter '*-transactions.csv' | 
Sort-Object -Property LastWriteTime -Descending | 
Select-Object -First 1
$filePath = $file.FullName
$fileName = $file.Name

try {
    Write-S3Object -BucketName $bucketName -File $filePath 

    Start-Sleep -Seconds 2

    $fileCheck = Get-S3Object -BucketName $bucketName -Key $fileName
    if (!$fileCheck) {
        Write-Warning "$fileName was not uploaded to $bucketName"
    }
    else {
        Write-Information "$fileName was uploaded to $bucketName" -InformationAction Continue
    }
} 
catch {
    Write-Error $_
}
