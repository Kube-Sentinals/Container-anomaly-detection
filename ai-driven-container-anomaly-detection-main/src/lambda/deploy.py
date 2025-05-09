import os
import boto3
import zipfile
from datetime import datetime
from ..utils.vault_config import VaultConfig

def create_lambda_package():
    """Create a ZIP package for the Lambda function."""
    # Create a temporary directory for packaging
    os.makedirs('lambda_package', exist_ok=True)
    
    # Copy the Lambda function code
    with open('src/lambda/anomaly_handler.py', 'r') as source:
        with open('lambda_package/anomaly_handler.py', 'w') as target:
            target.write(source.read())
    
    # Create ZIP file
    with zipfile.ZipFile('lambda_package.zip', 'w') as zipf:
        zipf.write('lambda_package/anomaly_handler.py', 'anomaly_handler.py')
    
    return 'lambda_package.zip'

def deploy_lambda():
    """Deploy the Lambda function and set up EventBridge rule."""
    try:
        # Initialize AWS clients
        lambda_client = boto3.client('lambda')
        events_client = boto3.client('events')
        iam_client = boto3.client('iam')
        
        # Get configuration from Vault
        vault = VaultConfig()
        role_arn = vault.get_secret('AWS_LAMBDA_ROLE_ARN')
        
        # Create Lambda package
        package_path = create_lambda_package()
        
        # Create or update Lambda function
        function_name = 'container-anomaly-detector'
        
        try:
            # Update existing function
            with open(package_path, 'rb') as file_data:
                lambda_client.update_function_code(
                    FunctionName=function_name,
                    ZipFile=file_data.read()
                )
        except lambda_client.exceptions.ResourceNotFoundException:
            # Create new function
            with open(package_path, 'rb') as file_data:
                lambda_client.create_function(
                    FunctionName=function_name,
                    Runtime='python3.8',
                    Handler='anomaly_handler.lambda_handler',
                    Role=role_arn,
                    Code={'ZipFile': file_data.read()},
                    Timeout=300,
                    MemorySize=256,
                    Environment={
                        'Variables': {
                            'S3_BUCKET_NAME': vault.get_secret('AWS_S3_BUCKET'),
                            'ECS_CLUSTER_NAME': vault.get_secret('AWS_ECS_CLUSTER'),
                            'SAGEMAKER_ENDPOINT': vault.get_secret('AWS_SAGEMAKER_ENDPOINT')
                        }
                    }
                )
        
        # Create EventBridge rule
        rule_name = 'container-anomaly-detection-rule'
        
        # Schedule: Run every 5 minutes
        schedule_expression = 'rate(5 minutes)'
        
        # Create or update the rule
        try:
            events_client.put_rule(
                Name=rule_name,
                ScheduleExpression=schedule_expression,
                State='ENABLED',
                Description='Triggers container anomaly detection every 5 minutes',
                Targets=[{
                    'Id': 'ContainerAnomalyDetection',
                    'Arn': lambda_client.get_function(FunctionName=function_name)['Configuration']['FunctionArn']
                }]
            )
        except events_client.exceptions.ResourceNotFoundException:
            events_client.create_rule(
                Name=rule_name,
                ScheduleExpression=schedule_expression,
                State='ENABLED',
                Description='Triggers container anomaly detection every 5 minutes',
                Targets=[{
                    'Id': 'ContainerAnomalyDetection',
                    'Arn': lambda_client.get_function(FunctionName=function_name)['Configuration']['FunctionArn']
                }]
            )
        
        # Add permission for EventBridge to invoke Lambda
        try:
            lambda_client.add_permission(
                FunctionName=function_name,
                StatementId='EventBridgeInvokeFunction',
                Action='lambda:InvokeFunction',
                Principal='events.amazonaws.com',
                SourceArn=events_client.describe_rule(Name=rule_name)['Arn']
            )
        except lambda_client.exceptions.ResourceConflictException:
            # Permission already exists
            pass
        
        print(f"Successfully deployed Lambda function '{function_name}' and EventBridge rule '{rule_name}'")
        
    except Exception as e:
        print(f"Error deploying Lambda function: {str(e)}")
        raise
    finally:
        # Clean up
        if os.path.exists('lambda_package.zip'):
            os.remove('lambda_package.zip')
        if os.path.exists('lambda_package'):
            import shutil
            shutil.rmtree('lambda_package')

if __name__ == "__main__":
    deploy_lambda() 