import os
import time
from datetime import datetime, timedelta
import pandas as pd
from splunklib.client import Service
from splunklib.results import JSONResultsReader
from ..utils.vault_config import VaultConfig

class SplunkCollector:
    def __init__(self):
        """Initialize Splunk collector with credentials from Vault."""
        self.vault = VaultConfig()
        
        # Get Splunk credentials from Vault
        self.splunk_host = self.vault.get_secret('SPLUNK_HOST')
        self.splunk_port = int(self.vault.get_secret('SPLUNK_PORT') or '8089')
        self.splunk_username = self.vault.get_secret('SPLUNK_USERNAME')
        self.splunk_password = self.vault.get_secret('SPLUNK_PASSWORD')
        
        if not all([self.splunk_host, self.splunk_username, self.splunk_password]):
            raise ValueError("Missing required Splunk credentials in Vault")
        
        self.service = Service(
            host=self.splunk_host,
            port=self.splunk_port,
            username=self.splunk_username,
            password=self.splunk_password
        )

    def collect_container_metrics(self, time_range_hours=24):
        """Collect container metrics from Splunk."""
        search_query = f"""
        search index=container_metrics 
        | stats avg(cpu_usage) as avg_cpu, 
                avg(memory_usage) as avg_memory,
                avg(disk_usage) as avg_disk,
                count by container_id, container_name
        | where _time > relative_time(now(), "-{time_range_hours}h")
        """
        
        try:
            job = self.service.jobs.create(search_query)
            while not job.is_done():
                time.sleep(2)
            
            results = []
            for result in JSONResultsReader(job.results()):
                results.append(result)
            
            return pd.DataFrame(results)
        
        except Exception as e:
            print(f"Error collecting metrics: {str(e)}")
            return None

    def save_metrics(self, df, output_path):
        """Save collected metrics to CSV file."""
        if df is not None:
            df.to_csv(output_path, index=False)
            print(f"Metrics saved to {output_path}")
        else:
            print("No metrics to save")

def main():
    collector = SplunkCollector()
    metrics_df = collector.collect_container_metrics()
    
    if metrics_df is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/container_metrics_{timestamp}.csv"
        os.makedirs("data", exist_ok=True)
        collector.save_metrics(metrics_df, output_path)

if __name__ == "__main__":
    main() 