import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
from tabulate import tabulate




class FeatureFlagsFetcher:
    def __init__(self):
        from api_tradezero.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token

        self.base_url = "https://api.tradezero.com/v1/featureflags/api/featureflags"
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

    def fetch(self):
        """發送 API 請求，獲取資料"""
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()  # Raises an error for bad status codes

            # Pretty-print the JSON response
            print("\n✅ Success! Response from /v1/featureflags/api/featureflags:")
            
            # Convert response to a list of dictionaries for tabulate
            if isinstance(response.json(), list):
                # If response is an array of feature flags
                table_data = []
                for item in response.json():
                    table_data.append([item.get('name', 'N/A'), item.get('value', 'N/A'), item.get('description', 'N/A')])
                
                print(tabulate(table_data, headers=["Feature Name", "Value", "Description"], tablefmt="grid"))
            else:
                # If response is a single object
                print(tabulate(response.json().items(), headers=["Key", "Value"], tablefmt="grid"))

        except requests.exceptions.RequestException as e:
            print(f"❌ Error making request: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Status Code: {e.response.status_code}")
                print(f"Response: {e.response.text}")

if __name__ == "__main__":
    fetcher = FeatureFlagsFetcher()
    fetcher.fetch()
