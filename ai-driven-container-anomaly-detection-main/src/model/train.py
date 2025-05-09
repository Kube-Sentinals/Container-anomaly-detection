import os
import boto3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from dotenv import load_dotenv

class AnomalyDetector:
    def __init__(self):
        load_dotenv()
        self.sagemaker = boto3.client('sagemaker')
        self.s3 = boto3.client('s3')
        self.model_name = "container-anomaly-detector"
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
    def prepare_data(self, data_path):
        """Prepare and preprocess the data."""
        df = pd.read_csv(data_path)
        
        # Select features for anomaly detection
        features = ['avg_cpu', 'avg_memory', 'avg_disk']
        X = df[features]
        
        # Scale the features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        return X_scaled, scaler
    
    def train_model(self, X):
        """Train the Isolation Forest model."""
        model = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        
        model.fit(X)
        return model
    
    def save_model(self, model, scaler, model_path):
        """Save the trained model and scaler."""
        import joblib
        model_data = {
            'model': model,
            'scaler': scaler
        }
        joblib.dump(model_data, model_path)
        
        # Upload to S3
        s3_path = f"s3://{self.bucket_name}/models/{self.model_name}/model.joblib"
        self.s3.upload_file(model_path, self.bucket_name, f"models/{self.model_name}/model.joblib")
        
        return s3_path
    
    def deploy_model(self, s3_path):
        """Deploy the model to SageMaker endpoint."""
        # Create model in SageMaker
        model_response = self.sagemaker.create_model(
            ModelName=self.model_name,
            PrimaryContainer={
                'Image': os.getenv('SAGEMAKER_IMAGE'),
                'ModelDataUrl': s3_path
            },
            ExecutionRoleArn=os.getenv('SAGEMAKER_ROLE_ARN')
        )
        
        # Create endpoint configuration
        endpoint_config_response = self.sagemaker.create_endpoint_config(
            EndpointConfigName=f"{self.model_name}-config",
            ProductionVariants=[{
                'InstanceType': 'ml.t2.medium',
                'InitialInstanceCount': 1,
                'ModelName': self.model_name,
                'VariantName': 'AllTraffic'
            }]
        )
        
        # Create endpoint
        endpoint_response = self.sagemaker.create_endpoint(
            EndpointName=self.model_name,
            EndpointConfigName=f"{self.model_name}-config"
        )
        
        return endpoint_response['EndpointArn']

def main():
    detector = AnomalyDetector()
    
    # Prepare data
    data_path = "data/container_metrics_latest.csv"
    X_scaled, scaler = detector.prepare_data(data_path)
    
    # Train model
    model = detector.train_model(X_scaled)
    
    # Save model
    model_path = "models/anomaly_detector.joblib"
    os.makedirs("models", exist_ok=True)
    s3_path = detector.save_model(model, scaler, model_path)
    
    # Deploy model
    endpoint_arn = detector.deploy_model(s3_path)
    print(f"Model deployed to endpoint: {endpoint_arn}")

if __name__ == "__main__":
    main() 