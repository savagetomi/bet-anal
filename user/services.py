# import requests
# import os

# class StakeDataClient:
#     """
#     Client for interacting with the Stake API for read-only data analysis.
#     """
#     def __init__(self, api_token=None):
#         # Fallback to env var, but allowing injection for flexibility
#         self.api_token = api_token or os.environ.get('STAKE_API_TOKEN')
#         self.base_url = "https://api.stake.com" 

#     def _get_headers(self):
#         if not self.api_token:
#             raise ValueError("API Token is not configured.")
#         return {
#             "Authorization": f"Bearer {self.api_token}",
#             "Content-Type": "application/json"
#         }

#     def get_bet_history(self):
#         """
#         Fetch historical bet data.
#         """
#         # Note: Replace with actual endpoint
#         url = f"{self.base_url}/v1/bets"
#         response = requests.get(url, headers=self._get_headers())
        
#         # Raise an exception for bad status codes (4xx or 5xx)
#         response.raise_for_status() 
        
#         return response.json()
