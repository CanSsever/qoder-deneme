/**
 * Test script to verify login fix and backend connectivity
 */

const { createOneShotClient } = require('./frontend/oneshot-sdk');

async function testLoginFix() {
    console.log("[TOOLS] Testing Login Fix - Comprehensive Test");
    console.log("=".repeat(50));
    
    // Test Configuration
    const config = {
        baseUrl: 'http://192.168.1.210:8000',
        timeout: 30000,
        retryAttempts: 10,
        retryDelay: 1000
    };
    
    console.log("[DOCS] Configuration:");
    console.log(`   Base URL: ${config.baseUrl}`);
    console.log(`   Timeout: ${config.timeout}ms`);
    console.log(`   Max Retries: ${config.retryAttempts}`);
    console.log("");
    
    const client = createOneShotClient(config);
    
    // Step 1: Test Backend Connectivity
    console.log("1 Testing Backend Connectivity...");
    try {
        const startTime = Date.now();
        const healthCheck = await client.healthCheck();
        const responseTime = Date.now() - startTime;
        
        console.log("   [OK] Backend is reachable!");
        console.log(`   [TIMER]  Response time: ${responseTime}ms`);
        console.log(`   [METRICS] Health status: ${healthCheck.status}`);
        console.log(`   [TAG]  Service: ${healthCheck.service} v${healthCheck.version}`);
        console.log("");
    } catch (error) {
        console.error("   [FAIL] Backend connectivity failed:");
        console.error(`   Error: ${error.message}`);
        return false;
    }
    
    // Step 2: Test Network Quality Assessment
    console.log("2 Assessing Network Quality...");
    try {
        const networkQuality = await client.getNetworkQuality();
        console.log(`   [RADAR] Network Quality: ${networkQuality.quality}`);
        console.log(`   [TIMER]  Latency: ${networkQuality.metrics.latency}ms`);
        console.log(`   [REFRESH] Recommended timeout: ${networkQuality.recommendedTimeout}ms`);
        console.log(`   [RETRY] Max retries: ${networkQuality.maxRetries}`);
        console.log("");
    } catch (error) {
        console.warn("   [WARN]  Network assessment failed, using defaults");
        console.warn(`   Error: ${error.message}`);
        console.log("");
    }
    
    // Step 3: Test User Registration (if needed)
    console.log("3 Testing User Registration...");
    const testEmail = `test-${Date.now()}@example.com`;
    const testPassword = "SecureTest123!";
    
    try {
        const registrationResult = await client.register(
            testEmail, 
            testPassword,
            {
                onProgress: (message) => {
                    console.log(`   [DOCS] ${message}`);
                }
            }
        );
        
        console.log("   [OK] Registration successful!");
        console.log(`   [USER] User ID: ${registrationResult.user.id}`);
        console.log(`   [EMAIL] Email: ${registrationResult.user.email}`);
        console.log(`   [TICKET] Access token received: ${registrationResult.access_token ? 'Yes' : 'No'}`);
        console.log("");
        
        // Logout to test login separately
        client.logout();
        
    } catch (error) {
        console.error("   [FAIL] Registration failed:");
        console.error(`   Error: ${error.message}`);
        if (error.classification) {
            console.error(`   Category: ${error.classification.category}`);
            console.error(`   User Message: ${error.classification.userMessage}`);
        }
        return false;
    }
    
    // Step 4: Test User Login
    console.log("4 Testing User Login...");
    try {
        const loginResult = await client.login(
            testEmail, 
            testPassword,
            {
                onProgress: (message) => {
                    console.log(`   [DOCS] ${message}`);
                },
                maxAttempts: 10
            }
        );
        
        console.log("   [OK] Login successful!");
        console.log(`   [USER] User ID: ${loginResult.user.id}`);
        console.log(`   [EMAIL] Email: ${loginResult.user.email}`);
        console.log(`   [TICKET] Access token received: ${loginResult.access_token ? 'Yes' : 'No'}`);
        console.log(`   [SECURE] Authentication status: ${client.isAuth() ? 'Authenticated' : 'Not Authenticated'}`);
        console.log("");
        
    } catch (error) {
        console.error("   [FAIL] Login failed:");
        console.error(`   Error: ${error.message}`);
        if (error.classification) {
            console.error(`   Category: ${error.classification.category}`);
            console.error(`   User Message: ${error.classification.userMessage}`);
            console.error(`   Should retry: ${error.classification.retryRecommended}`);
        }
        return false;
    }
    
    // Step 5: Test Authenticated Endpoint
    console.log("5 Testing Authenticated Endpoint...");
    try {
        const userProfile = await client.getMe();
        console.log("   [OK] Profile retrieval successful!");
        console.log(`   [USER] User ID: ${userProfile.id}`);
        console.log(`   [EMAIL] Email: ${userProfile.email}`);
        console.log("");
    } catch (error) {
        console.error("   [FAIL] Profile retrieval failed:");
        console.error(`   Error: ${error.message}`);
        return false;
    }
    
    // Step 6: Test User Limits
    console.log("6 Testing User Limits...");
    try {
        const limits = await client.getUserLimits();
        console.log("   [OK] Limits retrieval successful!");
        console.log(`   [METRICS] Limits:`, limits);
        console.log("");
    } catch (error) {
        console.error("   [FAIL] Limits retrieval failed:");
        console.error(`   Error: ${error.message}`);
        console.log("");
    }
    
    console.log("[CELEBRATE] All tests completed successfully!");
    console.log("[OK] Login error has been resolved!");
    console.log("");
    console.log("[MOBILE] Your mobile app should now be able to:");
    console.log("   -  Connect to the backend server");
    console.log("   -  Register new user accounts");
    console.log("   -  Login with existing credentials");
    console.log("   -  Access authenticated endpoints");
    console.log("   -  Handle network timeouts gracefully");
    console.log("");
    
    return true;
}

// Run the test
testLoginFix()
    .then(success => {
        if (success) {
            console.log("[TROPHY] TEST PASSED - Login fix verified!");
            process.exit(0);
        } else {
            console.log("[BOOM] TEST FAILED - Issues still remain");
            process.exit(1);
        }
    })
    .catch(error => {
        console.error("[BOOM] TEST CRASHED:", error);
        process.exit(1);
    });
