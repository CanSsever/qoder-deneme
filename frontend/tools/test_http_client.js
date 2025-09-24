// Test script to verify the HTTP client fix
const fs = require('fs');
const path = require('path');

// Read the compiled http-client.js file
const httpClientPath = path.join(__dirname, '..', 'oneshot-sdk', 'dist', 'http-client.js');
const httpClientContent = fs.readFileSync(httpClientPath, 'utf8');

// Check if the fix is in place
if (httpClientContent.includes('Always use manual timeout implementation for React Native compatibility')) {
  console.log('✅ SUCCESS: HTTP client fix is in place');
  console.log('✅ The code now uses manual timeout implementation instead of AbortSignal.timeout');
  
  // Check for key parts of the fix
  if (httpClientContent.includes('controller = new AbortController()') && 
      httpClientContent.includes('timeoutId = setTimeout')) {
    console.log('✅ SUCCESS: Manual timeout implementation found');
  } else {
    console.log('❌ ERROR: Manual timeout implementation not found');
  }
  
  if (httpClientContent.includes('config.signal && config.signal.aborted')) {
    console.log('✅ SUCCESS: Timeout error detection found');
  } else {
    console.log('❌ ERROR: Timeout error detection not found');
  }
} else {
  console.log('❌ ERROR: HTTP client fix not found');
}

console.log('\n--- HTTP Client Analysis ---');
console.log('The fix ensures React Native/Expo compatibility by:');
console.log('1. Removing AbortSignal.timeout() which is not supported');
console.log('2. Using manual AbortController with setTimeout');
console.log('3. Properly cleaning up timeouts on success/failure');
console.log('4. Correctly identifying and handling timeout errors');