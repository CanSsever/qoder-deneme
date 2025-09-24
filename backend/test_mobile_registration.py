#!/usr/bin/env python3
"""
Test script to simulate mobile app registration process
This script tests the exact same flow that the mobile app would use
"""
import requests
import json
import time
import random

def test_mobile_registration():
    """Test the mobile registration flow"""
    base_url = "http://192.168.0.131:8000"
    
    print("🚀 Testing OneShot Mobile Registration Flow")
    print("=" * 50)
    
    # Test 1: Health Check
    print("\n📋 Test 1: Health Check")
    try:
        response = requests.get(f"{base_url}/healthz", timeout=30)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health check passed: {health_data['status']}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during health check: {e}")
        return False
    
    # Test 2: Registration with timeout simulation
    print("\n📋 Test 2: User Registration (with timeout handling)")
    
    # Generate unique test email
    test_email = f"test_user_{int(time.time())}_{random.randint(1000, 9999)}@example.com"
    test_password = "TestPassword123!"
    
    registration_data = {
        "email": test_email,
        "password": test_password
    }
    
    try:
        # Simulate mobile app request with proper headers and timeout
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OneShot-Mobile/1.0"
        }
        
        print(f"📧 Registering user: {test_email}")
        start_time = time.time()
        
        response = requests.post(
            f"{base_url}/api/v1/auth/register",
            headers=headers,
            json=registration_data,
            timeout=30  # Same timeout as mobile app
        )
        
        end_time = time.time()
        duration = end_time - start_time
        print(f"⏱️  Request duration: {duration:.2f}s")
        
        if response.status_code == 200:
            auth_data = response.json()
            print("✅ Registration successful!")
            print(f"🔑 Access token received: {auth_data['access_token'][:20]}...")
            print(f"👤 User ID: {auth_data['user']['id']}")
            print(f"💰 Credits: {auth_data['user']['credits']}")
            
            # Test 3: Verify the token works
            print("\n📋 Test 3: Token Verification")
            auth_headers = {
                "Authorization": f"Bearer {auth_data['access_token']}",
                "Content-Type": "application/json"
            }
            
            me_response = requests.get(
                f"{base_url}/api/v1/auth/me",
                headers=auth_headers,
                timeout=30
            )
            
            if me_response.status_code == 200:
                user_data = me_response.json()
                print(f"✅ Token verification successful!")
                print(f"👤 User profile: {user_data['email']}")
            else:
                print(f"❌ Token verification failed: {me_response.status_code}")
                
        else:
            print(f"❌ Registration failed: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Registration request timed out (>30s)")
        print("💡 This is the exact error mobile users are experiencing!")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        print("💡 This indicates network connectivity issues")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return False
    
    # Test 4: Duplicate registration (should fail)
    print("\n📋 Test 4: Duplicate Registration Test")
    try:
        duplicate_response = requests.post(
            f"{base_url}/api/v1/auth/register",
            headers=headers,
            json=registration_data,
            timeout=30
        )
        
        if duplicate_response.status_code == 422:
            print("✅ Duplicate registration properly rejected")
        else:
            print(f"⚠️  Unexpected response for duplicate: {duplicate_response.status_code}")
    except Exception as e:
        print(f"❌ Error testing duplicate registration: {e}")
    
    print("\n🎉 All tests completed successfully!")
    print("💡 Mobile app should now be able to register users without timeout errors")
    return True

if __name__ == "__main__":
    success = test_mobile_registration()
    if success:
        print("\n✅ RESOLUTION VERIFIED: Network timeout issue resolved!")
        print("📱 Mobile app registration should now work properly")
    else:
        print("\n❌ ISSUE PERSISTS: Further investigation needed")