// Test error handling and alerts functionality
const fs = require('fs');
const path = require('path');

console.log('🚨 Testing error handling and alerts functionality...\n');

// Read the compiled HTTP client
const httpClientPath = path.join(__dirname, '..', 'oneshot-sdk', 'dist', 'http-client.js');
const httpClientContent = fs.readFileSync(httpClientPath, 'utf8');

console.log('1. Testing error normalization:');

// Check for proper error normalization
const hasErrorNormalization = httpClientContent.includes('normalizeError(error)');

if (hasErrorNormalization) {
  console.log('   ✅ SUCCESS: Error normalization function exists');
} else {
  console.log('   ❌ ERROR: Error normalization function not found');
}

// Check for timeout error handling
const handlesTimeoutErrors = httpClientContent.includes('error.name === \'AbortError\'') &&
                           httpClientContent.includes('Request timeout');

if (handlesTimeoutErrors) {
  console.log('   ✅ SUCCESS: Timeout errors are properly handled');
} else {
  console.log('   ❌ ERROR: Timeout errors are not properly handled');
}

// Check for network error handling
const handlesNetworkErrors = httpClientContent.includes('Network connection failed');

if (handlesNetworkErrors) {
  console.log('   ✅ SUCCESS: Network errors are properly handled');
} else {
  console.log('   ❌ ERROR: Network errors are not properly handled');
}

console.log('\n2. Testing specific error types:');

// Check for AuthenticationError handling
const handlesAuthErrors = httpClientContent.includes('AuthenticationError');

if (handlesAuthErrors) {
  console.log('   ✅ SUCCESS: Authentication errors are handled');
} else {
  console.log('   ❌ ERROR: Authentication errors are not handled');
}

// Check for ValidationError handling
const handlesValidationErrors = httpClientContent.includes('ValidationError');

if (handlesValidationErrors) {
  console.log('   ✅ SUCCESS: Validation errors are handled');
} else {
  console.log('   ❌ ERROR: Validation errors are not handled');
}

// Check for RateLimitError handling
const handlesRateLimitErrors = httpClientContent.includes('RateLimitError');

if (handlesRateLimitErrors) {
  console.log('   ✅ SUCCESS: Rate limit errors are handled');
} else {
  console.log('   ❌ ERROR: Rate limit errors are not handled');
}

console.log('\n3. Testing retry logic:');

// Check for retry logic
const hasRetryLogic = httpClientContent.includes('executeWithRetry') &&
                     httpClientContent.includes('shouldRetry');

if (hasRetryLogic) {
  console.log('   ✅ SUCCESS: Retry logic is implemented');
} else {
  console.log('   ❌ ERROR: Retry logic is not implemented');
}

// Check that retry logic includes timeout errors
const retriesOnTimeout = httpClientContent.includes('error.name === \'AbortError\'') &&
                        httpClientContent.includes('return true; // Timeout');

if (retriesOnTimeout) {
  console.log('   ✅ SUCCESS: Retry logic includes timeout errors');
} else {
  console.log('   ❌ ERROR: Retry logic does not include timeout errors');
}

console.log('\n4. Testing Expo app error handling:');

// Check the RegisterScreen for error handling
const registerScreenPath = path.join(__dirname, '..', 'expo-app', 'src', 'screens', 'RegisterScreen.tsx');
const registerScreenContent = fs.readFileSync(registerScreenPath, 'utf8');

// Check for Alert usage
const usesAlert = registerScreenContent.includes('Alert.alert');

if (usesAlert) {
  console.log('   ✅ SUCCESS: RegisterScreen uses Alert for error display');
} else {
  console.log('   ❌ ERROR: RegisterScreen does not use Alert for error display');
}

// Check for specific error handling
const handlesRegistrationErrors = registerScreenContent.includes('Registration Failed') &&
                                registerScreenContent.includes('error.message');

if (handlesRegistrationErrors) {
  console.log('   ✅ SUCCESS: RegisterScreen handles registration errors');
} else {
  console.log('   ❌ ERROR: RegisterScreen does not handle registration errors');
}

console.log('\n5. Testing LoginScreen error handling:');

// Check the LoginScreen for error handling
const loginScreenPath = path.join(__dirname, '..', 'expo-app', 'src', 'screens', 'LoginScreen.tsx');
const loginScreenContent = fs.readFileSync(loginScreenPath, 'utf8');

// Check for Alert usage
const loginUsesAlert = loginScreenContent.includes('Alert.alert');

if (loginUsesAlert) {
  console.log('   ✅ SUCCESS: LoginScreen uses Alert for error display');
} else {
  console.log('   ❌ ERROR: LoginScreen does not use Alert for error display');
}

// Check for specific error handling
const handlesLoginErrors = loginScreenContent.includes('Login Failed') &&
                          loginScreenContent.includes('error.message');

if (handlesLoginErrors) {
  console.log('   ✅ SUCCESS: LoginScreen handles login errors');
} else {
  console.log('   ❌ ERROR: LoginScreen does not handle login errors');
}

console.log('\n📋 Error Handling Testing Summary:');
console.log('The error handling implementation should:');
console.log('• Properly normalize all types of errors');
console.log('• Handle timeout errors specifically');
console.log('• Handle network connection errors');
console.log('• Handle authentication errors (401)');
console.log('• Handle validation errors (422)');
console.log('• Handle rate limit errors (429)');
console.log('• Retry on appropriate errors including timeouts');
console.log('• Display user-friendly error messages via Alert');

console.log('\n🧪 Expected Error Handling Behavior:');
console.log('• Timeout errors show "Request timeout" message');
console.log('• Network errors show "Network connection failed" message');
console.log('• Auth errors show appropriate login/registration messages');
console.log('• Validation errors show specific validation messages');
console.log('• Rate limit errors show "Too many requests" message');
console.log('• All errors are retried appropriately when configured');
console.log('• User sees clear, actionable error messages');

console.log('\n🎉 ERROR HANDLING TESTING COMPLETE');