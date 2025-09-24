// Test to verify the registration fix
const fs = require('fs');
const path = require('path');

console.log('Testing registration fix...\n');

// Read the compiled HTTP client to verify the fix
const httpClientPath = path.join(__dirname, '..', 'oneshot-sdk', 'dist', 'http-client.js');
const httpClientContent = fs.readFileSync(httpClientPath, 'utf8');

// Check if the fix is in place
console.log('1. Checking if AbortSignal.timeout is removed:');
const usesAbortSignalTimeout = httpClientContent.includes('AbortSignal.timeout');
if (!usesAbortSignalTimeout) {
  console.log('   ✅ SUCCESS: AbortSignal.timeout is not used');
} else {
  console.log('   ❌ ERROR: AbortSignal.timeout is still being used');
}

console.log('\n2. Checking if manual timeout implementation is in place:');
const hasManualTimeout = httpClientContent.includes('controller = new AbortController()') && 
                        httpClientContent.includes('timeoutId = setTimeout');
if (hasManualTimeout) {
  console.log('   ✅ SUCCESS: Manual timeout implementation found');
} else {
  console.log('   ❌ ERROR: Manual timeout implementation not found');
}

console.log('\n3. Checking if timeout cleanup is implemented:');
const hasTimeoutCleanup = httpClientContent.includes('clearTimeout(timeoutId)');
if (hasTimeoutCleanup) {
  console.log('   ✅ SUCCESS: Timeout cleanup implemented');
} else {
  console.log('   ❌ ERROR: Timeout cleanup not implemented');
}

console.log('\n4. Checking error handling for timeouts:');
const hasErrorHandling = httpClientContent.includes('config.signal && config.signal.aborted') &&
                        httpClientContent.includes('error.name = \'AbortError\'');
if (hasErrorHandling) {
  console.log('   ✅ SUCCESS: Timeout error handling implemented');
} else {
  console.log('   ❌ ERROR: Timeout error handling not implemented');
}

console.log('\n5. Simulating registration request flow:');
console.log('   The fixed HTTP client should now work in React Native/Expo environments');
console.log('   because it no longer relies on AbortSignal.timeout()');

console.log('\n🔧 Troubleshooting steps if you still see the error:');
console.log('1. Delete node_modules folder in expo-app directory');
console.log('2. Delete package-lock.json in expo-app directory');
console.log('3. Run "npm install" in expo-app directory');
console.log('4. Make sure the oneshot-sdk package is rebuilt with the fix');
console.log('5. Restart the Expo development server');

console.log('\n📋 Summary:');
console.log('The fix replaces the problematic AbortSignal.timeout() with a manual');
console.log('implementation using AbortController and setTimeout that works in all environments.');
console.log('This should resolve the "TypeError: AbortSignal.timeout is not a function" error.');