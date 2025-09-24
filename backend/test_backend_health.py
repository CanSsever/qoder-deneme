#!/usr/bin/env python3
"""
Simple script to test backend health endpoint accessibility
"""
import requests
import os
from urllib.parse import urljoin

def test_backend_health():
    # Test localhost access
    try:
        response = requests.get('http://localhost:8000/healthz', timeout=5)
        print("✅ Localhost access: SUCCESS")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text[:100]}...")
    except Exception as e:
        print("❌ Localhost access: FAILED")
        print(f"   Error: {e}")
    
    # Test LAN IP access (if available)
    # Try to read from .env file
    env_path = os.path.join('..', 'frontend', 'expo-app', '.env')
    api_url = None
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('API_URL='):
                    api_url = line.strip().split('=', 1)[1]
                    break
    
    if api_url:
        try:
            health_url = urljoin(api_url, '/healthz')
            response = requests.get(health_url, timeout=5)
            print(f"✅ LAN IP access ({api_url}): SUCCESS")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text[:100]}...")
        except Exception as e:
            print(f"❌ LAN IP access ({api_url}): FAILED")
            print(f"   Error: {e}")
    else:
        print("⚠️  LAN IP test: SKIPPED (API_URL not found in .env)")

if __name__ == "__main__":
    print("Testing backend health endpoint accessibility...")
    print("=" * 50)
    test_backend_health()
    print("=" * 50)
    print("Test complete. Check results above.")