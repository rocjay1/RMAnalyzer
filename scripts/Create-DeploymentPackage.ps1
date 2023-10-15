# Description: Creates a deployment package for the AWS Lambda function

$compress = @{
    Path = '.\dist\package\*', '.\dist\main.py', '.\config\config.json'
    CompressionLevel = 'Optimal'
    DestinationPath = '.\dist\dist.zip'
}

Compress-Archive @compress -Force