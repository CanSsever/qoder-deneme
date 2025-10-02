/**
 * Test script to verify login fix and backend connectivity
 */

const { createOneShotClient } = require('./frontend/oneshot-sdk');

async function testLoginFix() {
    console.log("🔧 Testing Login Fix - Comprehensive Test");
    console.log("=" .repeat(50));
    
    // Test Configuration
    const config = {
        baseUrl: 'http://192.168.1.210:8000',
        timeout: 30000,
        retryAttempts: 10,
        retryDelay: 1000
    };
    
    console.log("📋 Configuration:");
    console.log(`   Base URL: ${config.baseUrl}`);
    console.log(`   Timeout: ${config.timeout}ms`);
    console.log(`   Max Retries: ${config.retryAttempts}`);
    console.log("");
    
    const client = createOneShotClient(config);
    
    // Step 1: Test Backend Connectivity
    console.log("1️⃣ Testing Backend Connectivity...");
    try {
        const startTime = Date.now();
        const healthCheck = await client.healthCheck();
        const responseTime = Date.now() - startTime;
        
        console.log("   ✅ Backend is reachable!");
        console.log(`   ⏱️  Response time: ${responseTime}ms`);
        console.log(`   📊 Health status: ${healthCheck.status}`);
        console.log(`   🏷️  Service: ${healthCheck.service} v${healthCheck.version}`);
        console.log("");
    } catch (error) {
        console.error("   ❌ Backend connectivity failed:");
        console.error(`   Error: ${error.message}`);
        return false;
    }
    
    // Step 2: Test Network Quality Assessment
    console.log("2️⃣ Assessing Network Quality...");
    try {
        const networkQuality = await client.getNetworkQuality();
        console.log(`   📡 Network Quality: ${networkQuality.quality}`);
        console.log(`   ⏱️  Latency: ${networkQuality.metrics.latency}ms`);
        console.log(`   🔄 Recommended timeout: ${networkQuality.recommendedTimeout}ms`);
        console.log(`   🔁 Max retries: ${networkQuality.maxRetries}`);
        console.log("");
    } catch (error) {
        console.warn("   ⚠️  Network assessment failed, using defaults");
        console.warn(`   Error: ${error.message}`);
        console.log("");
    }
    
    // Step 3: Test User Registration (if needed)
    console.log("3️⃣ Testing User Registration...");
    const testEmail = `test-${Date.now()}@example.com`;
    const testPassword = "SecureTest123!";
    
    try {
        const registrationResult = await client.register(
            testEmail, 
            testPassword,
            {
                onProgress: (message) => {
                    console.log(`   📋 ${message}`);
                }
            }
        );
        
        console.log("   ✅ Registration successful!");
        console.log(`   👤 User ID: ${registrationResult.user.id}`);
        console.log(`   📧 Email: ${registrationResult.user.email}`);
        console.log(`   🎫 Access token received: ${registrationResult.access_token ? 'Yes' : 'No'}`);
        console.log("");
        
        // Logout to test login separately
        client.logout();
        
    } catch (error) {
        console.error("   ❌ Registration failed:");
        console.error(`   Error: ${error.message}`);
        if (error.classification) {
            console.error(`   Category: ${error.classification.category}`);
            console.error(`   User Message: ${error.classification.userMessage}`);
        }
        return false;
    }
    
    // Step 4: Test User Login
    console.log("4️⃣ Testing User Login...");
    try {
        const loginResult = await client.login(
            testEmail, 
            testPassword,
            {
                onProgress: (message) => {
                    console.log(`   📋 ${message}`);
                },
                maxAttempts: 10
            }
        );
        
        console.log("   ✅ Login successful!");
        console.log(`   👤 User ID: ${loginResult.user.id}`);
        console.log(`   📧 Email: ${loginResult.user.email}`);
        console.log(`   🎫 Access token received: ${loginResult.access_token ? 'Yes' : 'No'}`);
        console.log(`   🔐 Authentication status: ${client.isAuth() ? 'Authenticated' : 'Not Authenticated'}`);
        console.log("");
        
    } catch (error) {
        console.error("   ❌ Login failed:");
        console.error(`   Error: ${error.message}`);
        if (error.classification) {
            console.error(`   Category: ${error.classification.category}`);
            console.error(`   User Message: ${error.classification.userMessage}`);
            console.error(`   Should retry: ${error.classification.retryRecommended}`);
        }
        return false;
    }
    
    // Step 5: Test Authenticated Endpoint
    console.log("5️⃣ Testing Authenticated Endpoint...");
    try {
        const userProfile = await client.getMe();
        console.log("   ✅ Profile retrieval successful!");
        console.log(`   👤 User ID: ${userProfile.id}`);
        console.log(`   📧 Email: ${userProfile.email}`);
        console.log("");
    } catch (error) {
        console.error("   ❌ Profile retrieval failed:");
        console.error(`   Error: ${error.message}`);
        return false;
    }
    
    // Step 6: Test User Limits
    console.log("6️⃣ Testing User Limits...");
    try {
        const limits = await client.getUserLimits();
        console.log("   ✅ Limits retrieval successful!");
        console.log(`   📊 Limits:`, limits);
        console.log("");
    } catch (error) {
        console.error("   ❌ Limits retrieval failed:");
        console.error(`   Error: ${error.message}`);
        console.log("");
    }
    
    console.log("🎉 All tests completed successfully!");
    console.log("✅ Login error has been resolved!");
    console.log("");
    console.log("📱 Your mobile app should now be able to:");
    console.log("   • Connect to the backend server");
    console.log("   • Register new user accounts");
    console.log("   • Login with existing credentials");
    console.log("   • Access authenticated endpoints");
    console.log("   • Handle network timeouts gracefully");
    console.log("");
    
    return true;
}

// Run the test
testLoginFix()
    .then(success => {
        if (success) {
            console.log("🏆 TEST PASSED - Login fix verified!");
            process.exit(0);
        } else {
            console.log("💥 TEST FAILED - Issues still remain");
            process.exit(1);
        }
    })
    .catch(error => {
        console.error("💥 TEST CRASHED:", error);
        process.exit(1);
    });