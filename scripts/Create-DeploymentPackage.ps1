# Description: Creates a deployment package for the AWS Lambda function

$compress = @{
    Path = '.\dist\packages\*', '.\dist\main.py', '.\config\config.json'
    CompressionLevel = 'Optimal'
    DestinationPath = '.\dist\pkg.zip'
}

Compress-Archive @compress -Force