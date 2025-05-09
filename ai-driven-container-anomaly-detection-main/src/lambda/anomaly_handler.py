import os
import json
import boto3
import pandas as pd
from datetime import datetime, timedelta
from ..data_collection.splunk_collector import SplunkCollector
from ..model.train import AnomalyDetector
from ..utils.vault_config import VaultConfig

def lambda_handler(event, context):
    """Main Lambda handler that orchestrates the anomaly detection process."""
    try:
        # Initialize components
        vault = VaultConfig()
        collector = SplunkCollector()
        detector = AnomalyDetector()
        
        # Step 1: Collect metrics
        print("Collecting container metrics...")
        metrics_df = collector.collect_container_metrics(time_range_hours=1)  # Last hour of data
        
        if metrics_df is None:
            raise Exception("Failed to collect metrics")
            
        # Save metrics to S3
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3 = boto3.client('s3')
        bucket_name = os.getenv('S3_BUCKET_NAME')
        metrics_key = f"metrics/container_metrics_{timestamp}.csv"
        
        # Convert DataFrame to CSV and upload to S3
        csv_buffer = metrics_df.to_csv(index=False).encode()
        s3.put_object(Bucket=bucket_name, Key=metrics_key, Body=csv_buffer)
        
        # Step 2: Detect anomalies
        print("Detecting anomalies...")
        anomalies = detector.detect_anomalies(metrics_df)
        
        # Step 3: Handle anomalies
        if anomalies:
            print(f"Found {len(anomalies)} anomalies")
            handle_anomalies(anomalies)
        else:
            print("No anomalies detected")
            
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Anomaly detection completed successfully',
                'anomalies_found': len(anomalies) if anomalies else 0,
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def handle_anomalies(anomalies):
    """Handle detected anomalies by scaling containers and sending alerts."""
    try:
        # Initialize AWS clients
        ecs = boto3.client('ecs')
        sns = boto3.client('sns')
        
        # Get configuration from Vault
        vault = VaultConfig()
        topic_arn = vault.get_secret('AWS_SNS_TOPIC_ARN')
        
        # Group anomalies by container name
        container_anomalies = {}
        for anomaly in anomalies:
            container_name = anomaly['container_name']
            if container_name not in container_anomalies:
                container_anomalies[container_name] = []
            container_anomalies[container_name].append(anomaly)
        
        # Handle each container's anomalies
        for container_name, container_anomalies_list in container_anomalies.items():
            # Scale container if needed
            scale_container(ecs, container_name, container_anomalies_list)
            
            # Send alert
            send_alert(sns, topic_arn, container_name, container_anomalies_list)
            
    except Exception as e:
        print(f"Error handling anomalies: {str(e)}")
        raise

def scale_container(ecs, container_name, anomalies):
    """Scale the container based on anomaly severity."""
    try:
        # Get current service info
        cluster_name = os.getenv('ECS_CLUSTER_NAME')
        service_name = container_name  # Assuming service name matches container name
        
        # Calculate desired count based on anomalies
        current_service = ecs.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )['services'][0]
        
        current_count = current_service['desiredCount']
        
        # Scale up if multiple anomalies detected
        if len(anomalies) > 1:
            new_count = min(current_count * 2, 10)  # Double up to max 10
        else:
            new_count = min(current_count + 1, 10)  # Add one up to max 10
            
        if new_count != current_count:
            ecs.update_service(
                cluster=cluster_name,
                service=service_name,
                desiredCount=new_count
            )
            print(f"Scaled {service_name} from {current_count} to {new_count}")
            
    except Exception as e:
        print(f"Error scaling container {container_name}: {str(e)}")
        raise

def send_alert(sns, topic_arn, container_name, anomalies):
    """Send alert through SNS."""
    try:
        message = {
            'container_name': container_name,
            'anomalies': anomalies,
            'timestamp': datetime.now().isoformat()
        }
        
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject=f"Container Anomaly Alert: {container_name}"
        )
        
    except Exception as e:
        print(f"Error sending alert: {str(e)}")
        raise 