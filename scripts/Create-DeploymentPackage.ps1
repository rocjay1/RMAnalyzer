# Description: Creates a deployment package for the AWS Lambda function

$compress = @{
    Path = '.\dist\packages\*', '.\lambda_function\src\main.py', '.\config\'
    CompressionLevel = 'Optimal'
    DestinationPath = '.\dist\pkg.zip'
}

Compress-Archive @compress -Force