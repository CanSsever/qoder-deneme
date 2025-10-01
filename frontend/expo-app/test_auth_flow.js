/**
 * Test script to validate the enhanced authentication flow
 */
const { oneShotClient } = require('./src/utils/client');
const NetworkDiagnostics = require('./src/utils/networkDiagnostics').default;

async function testAuthenticationFlow() {
  console.log('🚀 Testing Enhanced Authentication Flow...\n');

  // Test 1: Network connectivity
  console.log('1. Testing network connectivity...');
  try {
    const connectivityResult = await NetworkDiagnostics.testConnectivity();
    if (connectivityResult.success) {
      console.log(`✅ Connectivity test passed (${connectivityResult.latency}ms)`);
    } else {
      console.log(`❌ Connectivity test failed: ${connectivityResult.error}`);
      return;
    }
  } catch (error) {
    console.log(`❌ Connectivity test error: ${error.message}`);
    return;
  }

  // Test 2: Authentication endpoint test
  console.log('\n2. Testing authentication endpoint...');
  try {
    const authTestResult = await NetworkDiagnostics.testAuthEndpoint();
    if (authTestResult.success) {
      console.log(`✅ Auth endpoint test passed (${authTestResult.latency}ms)`);
    } else {
      console.log(`❌ Auth endpoint test failed: ${authTestResult.error}`);
    }
  } catch (error) {
    console.log(`❌ Auth endpoint test error: ${error.message}`);
  }

  // Test 3: Valid login
  console.log('\n3. Testing valid login...');
  try {
    const loginResponse = await oneShotClient.login('testuser@example.com', 'testpass123');
    console.log(`✅ Login successful! User: ${loginResponse.user.email}, Credits: ${loginResponse.user.credits}`);
  } catch (error) {
    console.log(`❌ Login failed: ${error.message}`);
  }

  // Test 4: Invalid login (should fail gracefully)
  console.log('\n4. Testing invalid login (should fail gracefully)...');
  try {
    await oneShotClient.login('invalid@example.com', 'wrongpassword');
    console.log('❌ Invalid login should have failed');
  } catch (error) {
    console.log(`✅ Invalid login properly rejected: ${error.message}`);
  }

  // Test 5: Network diagnostics
  console.log('\n5. Generating network diagnostic report...');
  try {
    const diagnosticReport = await NetworkDiagnostics.generateDiagnosticReport();
    console.log('✅ Diagnostic Report:');
    console.log(`   API URL: ${diagnosticReport.networkInfo.apiUrl}`);
    console.log(`   Online: ${diagnosticReport.networkInfo.online}`);
    console.log(`   Connectivity: ${diagnosticReport.connectivityTest.success ? 'Good' : 'Failed'}`);
    console.log(`   Recommendations: ${diagnosticReport.recommendations.join(', ')}`);
  } catch (error) {
    console.log(`❌ Diagnostic report error: ${error.message}`);
  }

  console.log('\n🏁 Authentication flow testing completed!');
}

// Run the test
testAuthenticationFlow().catch(console.error);