/**
 * API connectivity check script
 * Usage: node scripts/check-api.js
 * 
 * Performs pre-flight health checks before starting the app
 */

// Node 22+ has built-in fetch

// Load API configuration from environment
const apiUrl = 
  process.env.EXPO_PUBLIC_API_URL_ANDROID ||
  process.env.EXPO_PUBLIC_API_URL_IOS ||
  process.env.EXPO_PUBLIC_API_URL_LAN ||
  process.env.EXPO_PUBLIC_API_URL_DEV ||
  process.env.EXPO_PUBLIC_API_URL ||
  'http://localhost:8000';

const timeout = parseInt(process.env.EXPO_PUBLIC_API_TIMEOUT || '5000', 10);

console.log(' Checking API connectivity...');
console.log(' API URL:', apiUrl);
console.log('  Timeout:', timeout + 'ms');
console.log('');

async function checkHealth() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const startTime = Date.now();
    const response = await fetch(`${apiUrl}/healthz`, {
      method: 'GET',
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    const latency = Date.now() - startTime;
    
    if (response.ok) {
      const data = await response.json();
      console.log(' Health check PASSED');
      console.log(' Status:', response.status);
      console.log(' Latency:', latency + 'ms');
      console.log(' Response:', JSON.stringify(data, null, 2));
      return true;
    } else {
      console.log(' Health check FAILED');
      console.log(' Status:', response.status);
      console.log(' Latency:', latency + 'ms');
      return false;
    }
  } catch (error) {
    clearTimeout(timeoutId);
    
    if (error.name === 'AbortError') {
      console.log(' Health check TIMEOUT');
      console.log(' The server did not respond within ' + timeout + 'ms');
    } else if (error.code === 'ECONNREFUSED') {
      console.log(' Connection REFUSED');
      console.log(' Is the backend server running on port 8000[FAIL]');
    } else if (error.code === 'ENOTFOUND') {
      console.log(' Host NOT FOUND');
      console.log(' Check the API URL:', apiUrl);
    } else {
      console.log(' Health check ERROR');
      console.log(' Error:', error.message);
    }
    
    return false;
  }
}

async function checkAuth() {
  console.log('');
  console.log(' Testing auth endpoint...');
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const startTime = Date.now();
    const response = await fetch(`${apiUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: 'test@example.com',
        password: 'invalid'
      }),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    const latency = Date.now() - startTime;
    
    if (response.status === 401) {
      console.log(' Auth endpoint is REACHABLE');
      console.log(' Status:', response.status, '(expected 401 for invalid credentials)');
      console.log(' Latency:', latency + 'ms');
      return true;
    } else {
      console.log('  Unexpected response from auth endpoint');
      console.log(' Status:', response.status);
      console.log(' Latency:', latency + 'ms');
      return false;
    }
  } catch (error) {
    clearTimeout(timeoutId);
    
    if (error.name === 'AbortError') {
      console.log(' Auth endpoint TIMEOUT');
    } else {
      console.log(' Auth endpoint ERROR');
      console.log(' Error:', error.message);
    }
    
    return false;
  }
}

async function main() {
  const healthOk = await checkHealth();
  const authOk = await checkAuth();
  
  console.log('');
  console.log('=' .repeat(50));
  
  if (healthOk && authOk) {
    console.log(' API is FULLY OPERATIONAL');
    console.log('');
    console.log('Next steps:');
    console.log('  1. Start the Expo app: npm start');
    console.log('  2. Run on Android: press "a"');
    console.log('  3. Run on iOS: press "i"');
    process.exit(0);
  } else {
    console.log(' API has ISSUES');
    console.log('');
    console.log('Troubleshooting:');
    console.log('  1. Start backend: cd backend && uvicorn apps.api.main:app --host 0.0.0.0 --port 8000');
    console.log('  2. Check firewall settings');
    console.log('  3. Verify .env configuration');
    console.log('  4. Check network connectivity');
    process.exit(1);
  }
}

main();
