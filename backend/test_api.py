"""
Comprehensive test suite for OneShot Face Swapper API
"""
import requests
import json
import time
from typing import Dict, Any

class OneShotAPITester:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v1"
        self.auth_token = None
        self.user_id = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status} {test_name}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        
    def test_health_check(self):
        """Test the health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health")
            success = response.status_code == 200 and response.json().get("status") == "healthy"
            self.log_test("Health Check", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Health Check", False, str(e))
            return False
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        try:
            response = requests.get(self.base_url)
            success = response.status_code == 200 and "OneShot" in response.json().get("message", "")
            self.log_test("Root Endpoint", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Root Endpoint", False, str(e))
            return False
    
    def test_user_registration(self):
        """Test user registration"""
        try:
            user_data = {
                "email": f"test_{int(time.time())}@example.com",
                "password": "testpassword123",
                "credits": 10
            }
            
            response = requests.post(
                f"{self.api_base}/auth/register",
                json=user_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
                success = bool(self.auth_token and self.user_id)
                self.log_test("User Registration", success, f"User ID: {self.user_id}")
                return success
            else:
                self.log_test("User Registration", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("User Registration", False, str(e))
            return False
    
    def test_user_login(self):
        """Test user login"""
        try:
            if not self.auth_token:
                self.log_test("User Login", False, "No user registered for login test")
                return False
                
            # First get user email from profile
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            profile_response = requests.get(f"{self.api_base}/auth/me", headers=headers)
            
            if profile_response.status_code != 200:
                self.log_test("User Login", False, "Could not get user profile")
                return False
                
            email = profile_response.json().get("email")
            
            # Now test login
            login_data = {
                "email": email,
                "password": "testpassword123"
            }
            
            response = requests.post(
                f"{self.api_base}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            success = response.status_code == 200 and "access_token" in response.json()
            self.log_test("User Login", success, f"Status: {response.status_code}")
            return success
            
        except Exception as e:
            self.log_test("User Login", False, str(e))
            return False
    
    def test_protected_endpoint(self):
        """Test accessing protected endpoint with authentication"""
        try:
            if not self.auth_token:
                self.log_test("Protected Endpoint", False, "No auth token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{self.api_base}/auth/me", headers=headers)
            
            success = response.status_code == 200 and "email" in response.json()
            details = f"Status: {response.status_code}"
            if success:
                user_data = response.json()
                details += f", Credits: {user_data.get('credits')}"
                
            self.log_test("Protected Endpoint (/auth/me)", success, details)
            return success
            
        except Exception as e:
            self.log_test("Protected Endpoint", False, str(e))
            return False
    
    def test_upload_presign(self):
        """Test upload presigned URL generation"""
        try:
            if not self.auth_token:
                self.log_test("Upload Presign", False, "No auth token available")
                return False
                
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
            
            upload_data = {
                "filename": "test_image.jpg",
                "content_type": "image/jpeg",
                "file_size": 1024000
            }
            
            response = requests.post(
                f"{self.api_base}/uploads/presign",
                json=upload_data,
                headers=headers
            )
            
            success = response.status_code == 200 and "presigned_url" in response.json()
            self.log_test("Upload Presign", success, f"Status: {response.status_code}")
            return success
            
        except Exception as e:
            self.log_test("Upload Presign", False, str(e))
            return False
    
    def test_job_creation(self):
        """Test AI job creation"""
        try:
            if not self.auth_token:
                self.log_test("Job Creation", False, "No auth token available")
                return False
                
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
            
            job_data = {
                "job_type": "face_restoration",
                "input_image_url": "https://example.com/test_image.jpg",
                "parameters": {
                    "model": "gfpgan",
                    "scale_factor": 2
                }
            }
            
            response = requests.post(
                f"{self.api_base}/jobs",
                json=job_data,
                headers=headers
            )
            
            if response.status_code == 200:
                job_info = response.json()
                job_id = job_info.get("job_id")
                success = bool(job_id)
                self.log_test("Job Creation", success, f"Job ID: {job_id}")
                
                # Test job status retrieval
                if job_id:
                    self.test_job_status(job_id)
                    
                return success
            else:
                self.log_test("Job Creation", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Job Creation", False, str(e))
            return False
    
    def test_job_status(self, job_id: str):
        """Test job status retrieval"""
        try:
            if not self.auth_token:
                self.log_test("Job Status", False, "No auth token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{self.api_base}/jobs/{job_id}", headers=headers)
            
            success = response.status_code == 200 and "status" in response.json()
            details = f"Status: {response.status_code}"
            if success:
                job_data = response.json()
                details += f", Job Status: {job_data.get('status')}"
                
            self.log_test("Job Status Retrieval", success, details)
            return success
            
        except Exception as e:
            self.log_test("Job Status", False, str(e))
            return False
    
    def test_job_list(self):
        """Test retrieving user job list"""
        try:
            if not self.auth_token:
                self.log_test("Job List", False, "No auth token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{self.api_base}/jobs", headers=headers)
            
            success = response.status_code == 200 and isinstance(response.json(), list)
            details = f"Status: {response.status_code}"
            if success:
                jobs = response.json()
                details += f", Jobs Count: {len(jobs)}"
                
            self.log_test("Job List Retrieval", success, details)
            return success
            
        except Exception as e:
            self.log_test("Job List", False, str(e))
            return False
    
    def test_billing_validation(self):
        """Test billing receipt validation"""
        try:
            if not self.auth_token:
                self.log_test("Billing Validation", False, "No auth token available")
                return False
                
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
            
            billing_data = {
                "receipt_data": "test_receipt_data_12345",
                "product_id": "credits_50",
                "transaction_id": f"test_transaction_{int(time.time())}"
            }
            
            response = requests.post(
                f"{self.api_base}/billing/validate",
                json=billing_data,
                headers=headers
            )
            
            success = response.status_code == 200 and "valid" in response.json()
            details = f"Status: {response.status_code}"
            if success:
                billing_result = response.json()
                details += f", Valid: {billing_result.get('valid')}, Credits Added: {billing_result.get('credits_added')}"
                
            self.log_test("Billing Validation", success, details)
            return success
            
        except Exception as e:
            self.log_test("Billing Validation", False, str(e))
            return False
    
    def test_unauthorized_access(self):
        """Test unauthorized access to protected endpoints"""
        try:
            # Test without token - should return 403
            response = requests.get(f"{self.api_base}/auth/me")
            no_token_ok = response.status_code == 403
            
            # Test with invalid token - should return 401
            headers = {"Authorization": "Bearer invalid_token_12345"}
            response2 = requests.get(f"{self.api_base}/auth/me", headers=headers)
            invalid_token_ok = response2.status_code == 401
            
            success = no_token_ok and invalid_token_ok
            details = f"No token: {response.status_code}, Invalid token: {response2.status_code}"
            
            self.log_test("Unauthorized Access Protection", success, details)
            return success
            
        except Exception as e:
            self.log_test("Unauthorized Access Protection", False, str(e))
            return False
    
    def test_input_validation(self):
        """Test input validation on endpoints"""
        try:
            # Test invalid email format with unique email
            invalid_user = {
                "email": "not_an_email_format",
                "password": "test",
                "credits": 10
            }
            
            response = requests.post(
                f"{self.api_base}/auth/register",
                json=invalid_user,
                headers={"Content-Type": "application/json"}
            )
            
            # Should return 422 for validation error
            email_validation_failed = response.status_code == 422
            
            # Test file size validation
            if self.auth_token:
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                }
                
                # Test file size too large
                large_file_data = {
                    "filename": "huge_file.jpg",
                    "content_type": "image/jpeg",
                    "file_size": 50 * 1024 * 1024  # 50MB - should exceed limit
                }
                
                upload_response = requests.post(
                    f"{self.api_base}/uploads/presign",
                    json=large_file_data,
                    headers=headers
                )
                
                size_validation_failed = upload_response.status_code >= 400
            else:
                size_validation_failed = True  # Skip if no token
            
            success = email_validation_failed and size_validation_failed
            details = f"Email validation: {response.status_code}, Size validation: {upload_response.status_code if self.auth_token else 'skipped'}"
            self.log_test("Input Validation", success, details)
            return success
            
        except Exception as e:
            self.log_test("Input Validation", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting OneShot Face Swapper API Test Suite")
        print("=" * 60)
        
        tests = [
            self.test_health_check,
            self.test_root_endpoint,
            self.test_user_registration,
            self.test_user_login,
            self.test_protected_endpoint,
            self.test_upload_presign,
            self.test_job_creation,
            self.test_job_list,
            self.test_billing_validation,
            self.test_unauthorized_access,
            self.test_input_validation
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
            print()  # Add spacing between tests
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        print(f"✅ Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("🎉 All tests passed! The API is functioning correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        print("\n🔍 Test Coverage:")
        print("✅ Authentication & Authorization")
        print("✅ User Management")
        print("✅ File Upload System") 
        print("✅ Job Processing")
        print("✅ Billing & Credits")
        print("✅ Input Validation")
        print("✅ Error Handling")
        
        return passed == total

if __name__ == "__main__":
    tester = OneShotAPITester()
    tester.run_all_tests()