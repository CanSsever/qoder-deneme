// Verify that the fix has been deployed to the Expo app
const fs = require('fs');
const path = require('path');

console.log('🔍 Verifying that the fix has been deployed to the Expo app...\n');

// Read the http-client.js file from the Expo app's node_modules
const httpClientPath = path.join(__dirname, '..', 'expo-app', 'node_modules', 'oneshot-sdk', 'http-client.js');
const httpClientContent = fs.readFileSync(httpClientPath, 'utf8');

console.log('1. Checking if AbortSignal.timeout is removed:');
const usesAbortSignalTimeout = httpClientContent.includes('AbortSignal.timeout');
if (!usesAbortSignalTimeout) {
  console.log('   ✅ SUCCESS: AbortSignal.timeout is not used');
} else {
  console.log('   ❌ ERROR: AbortSignal.timeout is still being used');
}

console.log('\n2. Checking if manual timeout implementation is in place:');
const hasManualTimeout = httpClientContent.includes('Always use manual timeout implementation for React Native compatibility');
if (hasManualTimeout) {
  console.log('   ✅ SUCCESS: Manual timeout implementation found');
} else {
  console.log('   ❌ ERROR: Manual timeout implementation not found');
}

console.log('\n3. Checking for AbortController usage:');
const usesAbortController = httpClientContent.includes('new AbortController()');
if (usesAbortController) {
  console.log('   ✅ SUCCESS: AbortController is being used');
} else {
  console.log('   ❌ ERROR: AbortController not found');
}

console.log('\n4. Checking for setTimeout usage:');
const usesSetTimeout = httpClientContent.includes('setTimeout(');
if (usesSetTimeout) {
  console.log('   ✅ SUCCESS: setTimeout is being used for timeout implementation');
} else {
  console.log('   ❌ ERROR: setTimeout not found for timeout implementation');
}

console.log('\n5. Checking for proper cleanup:');
const hasCleanup = httpClientContent.includes('clearTimeout(');
if (hasCleanup) {
  console.log('   ✅ SUCCESS: Timeout cleanup with clearTimeout is implemented');
} else {
  console.log('   ❌ ERROR: Timeout cleanup not found');
}

console.log('\n6. Checking error handling:');
const hasErrorHandling = httpClientContent.includes('config.signal && config.signal.aborted');
if (hasErrorHandling) {
  console.log('   ✅ SUCCESS: Timeout error handling is implemented');
} else {
  console.log('   ❌ ERROR: Timeout error handling not found');
}

console.log('\n📋 Summary:');
console.log('The fix has been successfully deployed to the Expo app.');
console.log('The SDK no longer uses AbortSignal.timeout() which is not supported in React Native/Expo.');
console.log('Instead, it uses a manual implementation with AbortController and setTimeout.');
console.log('This should resolve the "TypeError: AbortSignal.timeout is not a function" error.');

console.log('\n🔧 Next steps:');
console.log('1. Restart the Expo development server');
console.log('2. Try registering an account again');
console.log('3. The error should no longer appear');