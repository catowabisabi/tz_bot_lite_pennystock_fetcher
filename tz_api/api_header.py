
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class AuthHeader:
    def __init__(self, token=None):
        from tz_api.api_auth import TzAuth
        self.tz_auth = TzAuth()
        self.jwt_token = self.tz_auth.jwt_token

        
        self.headers = {
                "Authorization": self.jwt_token,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Origin": "https://standard.tradezeroweb.co/",
                "Referer": "https://standard.tradezeroweb.co/",
                "Connection": "keep-alive",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty"
            }

    def get_headers(self):
        return self.headers


if __name__ == "__main__":
    headers = AuthHeader().get_headers()
    #print(tabulate(headers.items(), headers=["Header", "Value"]))