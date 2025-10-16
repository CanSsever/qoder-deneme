/**
 * Simple test to verify SDK functionality with the backend
 */
import { OneShotClient } from '../oneshot-sdk/src/client';

const API_URL = 'http://192.168.1.210:8000';

async function testSDK() {
  console.log('[TOOLS] Testing OneShot SDK...\n');

  // Create client
  const client = new OneShotClient({
    baseUrl: API_URL,
    timeout: 10000,
    retryAttempts: 3,
    retryDelay: 1000
  });

  // Test health check
  console.log('1. Testing health check...');
  try {
    const health = await client.healthCheck();
    console.log(`[OK] Health check passed: ${health.service} v${health.version}`);
  } catch (error) {
    console.log(`[FAIL] Health check failed: ${error.message}`);
    return;
  }

  // Test login with valid credentials
  console.log('\n2. Testing login with valid credentials...');
  try {
    const response = await client.login('testuser@example.com', 'testpass123');
    console.log(`[OK] Login successful: ${response.user.email} (${response.user.credits} credits)`);
  } catch (error) {
    console.log(`[FAIL] Login failed: ${error.message}`);
  }

  // Test login with invalid credentials
  console.log('\n3. Testing login with invalid credentials...');
  try {
    await client.login('invalid@example.com', 'wrongpass');
    console.log('[FAIL] Should have failed!');
  } catch (error) {
    console.log(`[OK] Invalid login properly rejected: ${error.message}`);
  }

  console.log('\n[FLAG] SDK testing completed!');
}

testSDK().catch(console.error);