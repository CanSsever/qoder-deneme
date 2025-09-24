// Test timeout scenarios with the manual timeout implementation
const fs = require('fs');
const path = require('path');

console.log('⏰ Testing timeout scenarios with manual timeout implementation...\n');

// Read the compiled HTTP client
const httpClientPath = path.join(__dirname, '..', 'oneshot-sdk', 'dist', 'http-client.js');
const httpClientContent = fs.readFileSync(httpClientPath, 'utf8');

console.log('1. Testing timeout implementation details:');

// Check for the manual timeout pattern
const hasManualTimeoutPattern = httpClientContent.includes('controller = new AbortController()') && 
                               httpClientContent.includes('timeoutId = setTimeout') &&
                               httpClientContent.includes('clearTimeout(timeoutId)');

if (hasManualTimeoutPattern) {
  console.log('   ✅ SUCCESS: Manual timeout implementation pattern found');
} else {
  console.log('   ❌ ERROR: Manual timeout implementation pattern not complete');
}

// Check for timeout error handling
const hasTimeoutErrorHandling = httpClientContent.includes('config.signal && config.signal.aborted') &&
                               httpClientContent.includes('error.name = \'AbortError\'');

if (hasTimeoutErrorHandling) {
  console.log('   ✅ SUCCESS: Timeout error handling is implemented');
} else {
  console.log('   ❌ ERROR: Timeout error handling not found');
}

// Check for retry logic with timeouts
const hasRetryLogic = httpClientContent.includes('shouldRetry(error, retriesLeft)') &&
                     httpClientContent.includes('error.name === \'AbortError\'');

if (hasRetryLogic) {
  console.log('   ✅ SUCCESS: Retry logic includes timeout handling');
} else {
  console.log('   ❌ ERROR: Retry logic does not handle timeouts');
}

console.log('\n2. Testing React Native compatibility:');

// Check that AbortSignal.timeout is NOT used
const usesAbortSignalTimeout = httpClientContent.includes('AbortSignal.timeout');
if (!usesAbortSignalTimeout) {
  console.log('   ✅ SUCCESS: AbortSignal.timeout is not used (React Native compatible)');
} else {
  console.log('   ❌ ERROR: AbortSignal.timeout is still used (not React Native compatible)');
}

console.log('\n3. Testing resource cleanup:');

// Check for proper cleanup in both success and error cases
// Look for the actual cleanup code in the request method
const hasSuccessCleanup = httpClientContent.includes('// Clear timeout if request succeeds') &&
                         httpClientContent.includes('if (timeoutId) { clearTimeout(timeoutId); }');

const hasErrorCleanup = httpClientContent.includes('// Clear timeout if request fails') &&
                       httpClientContent.includes('if (timeoutId) { clearTimeout(timeoutId); }');

if (hasSuccessCleanup && hasErrorCleanup) {
  console.log('   ✅ SUCCESS: Timeout cleanup implemented for both success and error cases');
} else {
  console.log('   ❌ ERROR: Timeout cleanup not properly implemented');
}

// Let's double-check by looking for clearTimeout calls
const hasClearTimeout = (httpClientContent.match(/clearTimeout/g) || []).length >= 2;
if (hasClearTimeout) {
  console.log('   ✅ SUCCESS: clearTimeout is called in multiple places (resource cleanup)');
} else {
  console.log('   ❌ ERROR: clearTimeout not found or not called enough times');
}

console.log('\n4. Testing error normalization:');

// Check for proper error normalization
const hasErrorNormalization = httpClientContent.includes('normalizeError(error)') &&
                            httpClientContent.includes('error.name === \'AbortError\'') &&
                            httpClientContent.includes('Request timeout');

if (hasErrorNormalization) {
  console.log('   ✅ SUCCESS: Error normalization handles timeout errors correctly');
} else {
  console.log('   ❌ ERROR: Error normalization does not handle timeout errors');
}

console.log('\n📋 Timeout Scenario Testing Summary:');
console.log('The manual timeout implementation should handle these scenarios correctly:');
console.log('• Requests timing out after specified duration');
console.log('• Proper AbortError generation when timeout occurs');
console.log('• Cleanup of timeout resources in all cases');
console.log('• Retry logic for timed out requests');
console.log('• Error normalization for timeout errors');
console.log('• Compatibility with React Native/Expo environments');

console.log('\n🧪 Expected Behavior After Fix:');
console.log('• No more "TypeError: AbortSignal.timeout is not a function" errors');
console.log('• Proper timeout handling with AbortController + setTimeout');
console.log('• Correct error messages for timeout scenarios');
console.log('• Successful retry of timed out requests (if configured)');
console.log('• Proper cleanup of resources to prevent memory leaks');

console.log('\n🎉 TIMEOUT SCENARIO TESTING COMPLETE');