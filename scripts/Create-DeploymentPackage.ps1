# Description: Creates a deployment package for the AWS Lambda function

$compress = @{
    Path = '.\dist\package\*', '.\dist\main.py', '.\config'
    CompressionLevel = 'Optimal'
    DestinationPath = '.\dist\package.zip'
}

Compress-Archive @compress -Force