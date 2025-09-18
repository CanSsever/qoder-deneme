"""
Debug script to check actual HTTP status codes
"""
import requests

def check_status_codes():
    base_url = "http://127.0.0.1:8000/api/v1"
    
    print("🔍 Debugging HTTP Status Codes")
    print("=" * 40)
    
    # Test 1: No authentication header
    try:
        response = requests.get(f"{base_url}/auth/me")
        print(f"No Auth Header: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"No Auth Header Error: {e}")
    
    print("-" * 40)
    
    # Test 2: Invalid token
    try:
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = requests.get(f"{base_url}/auth/me", headers=headers)
        print(f"Invalid Token: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Invalid Token Error: {e}")
    
    print("-" * 40)
    
    # Test 3: Invalid email registration
    try:
        invalid_user = {
            "email": "invalid_email",
            "password": "test",
            "credits": 10
        }
        response = requests.post(
            f"{base_url}/auth/register",
            json=invalid_user,
            headers={"Content-Type": "application/json"}
        )
        print(f"Invalid Email: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Invalid Email Error: {e}")

if __name__ == "__main__":
    check_status_codes()