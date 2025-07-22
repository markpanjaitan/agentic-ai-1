import requests
import json
import time
from typing import Optional

# Import configuration
from config import GET_TOKEN_URL, USERNAME, PASSWORD, TENANT_ID, USER_SOURCE_ID

class TokenManager:
    _instance = None # Singleton instance
    _token = None
    _expiry_time = 0 # Unix timestamp

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TokenManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            print("TokenManager: Initialized.")

    def _fetch_new_token(self) -> Optional[str]:
        """
        Fetches a new authentication token from the getTokenUrl.
        Extracts 'access_token' and uses 'expire_in' for expiry calculation.
        """
        headers = {
            'Content-Type': 'application/json',
            'x-mo-tenant-id': TENANT_ID,
            'x-mo-user-source-id': USER_SOURCE_ID
        }
        data = {
            "username": USERNAME,
            "password": PASSWORD
        }
        
        print("TokenManager: Attempting to fetch a new token...")
        try:
            response = requests.post(GET_TOKEN_URL, headers=headers, data=json.dumps(data))
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            token_response = response.json()
            
            token = token_response.get('access_token')
            # Extract the expiry duration from "expire_in"
            expire_in = token_response.get('expire_in')
            
            if token and isinstance(expire_in, (int, float)):
                self._token = token
                # Set expiry time to current time + expire_in seconds
                # Subtracting a small buffer (e.g., 60 seconds) is good practice
                # to refresh *before* it truly expires, avoiding race conditions.
                self._expiry_time = time.time() + expire_in - 60
                print(f"TokenManager: New token fetched successfully. Expires in {expire_in} seconds.")
                return self._token
            else:
                print(f"TokenManager: Token or expiry information missing/invalid in response: {token_response}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"TokenManager: Error fetching token: {e}")
            return None
        except json.JSONDecodeError:
            print(f"TokenManager: Failed to decode JSON response: {response.text}")
            return None

    def get_token(self) -> Optional[str]:
        """
        Returns a valid token, fetching a new one if the current one is expired or not available.
        """
        # If no token, or token is expired, fetch a new one
        if not self._token or time.time() >= self._expiry_time:
            print("TokenManager: Current token is expired or not available. Fetching a new one.")
            return self._fetch_new_token()
        else:
            print(f"TokenManager: Using existing valid token (expires in {int(self._expiry_time - time.time())} seconds).")
            return self._token

# Make it a singleton instance
token_manager = TokenManager()