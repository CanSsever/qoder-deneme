// Test script to verify mobile app can connect to backend
const fs = require('fs');
const path = require('path');

console.log('🔍 Testing mobile app connection to backend...\n');

// Read the .env file
const envPath = path.join(__dirname, '.env');
let envContent = '';
try {
  envContent = fs.readFileSync(envPath, 'utf8');
  console.log('1. Reading .env file:');
  console.log('   ✅ .env file found');
} catch (err) {
  console.log('1. Reading .env file:');
  console.log('   ❌ .env file not found');
  console.log('   ℹ️  Copy .env.example to .env and configure it');
  process.exit(1);
}

// Extract API_URL from .env
const apiUrlMatch = envContent.match(/API_URL=(.*)/);
let apiUrl = '';
if (apiUrlMatch && apiUrlMatch[1]) {
  apiUrl = apiUrlMatch[1].trim();
  console.log(`   API_URL: ${apiUrl}`);
} else {
  console.log('   ❌ API_URL not found in .env');
  process.exit(1);
}

// Read app.json to verify extra config
const appJsonPath = path.join(__dirname, 'app.json');
try {
  const appJsonContent = fs.readFileSync(appJsonPath, 'utf8');
  const appConfig = JSON.parse(appJsonContent);
  
  console.log('\n2. Checking app.json configuration:');
  if (appConfig.expo && appConfig.expo.extra && appConfig.expo.extra.apiUrl) {
    console.log('   ✅ API URL configured in app.json extra section');
    console.log(`   app.json API_URL: ${appConfig.expo.extra.apiUrl}`);
  } else {
    console.log('   ❌ API URL not configured in app.json extra section');
    console.log('   ℹ️  Add "extra": {"apiUrl": "http://YOUR_IP:8000"} to app.json');
  }
} catch (err) {
  console.log('\n2. Checking app.json configuration:');
  console.log('   ❌ Could not read app.json');
}

// Verify the IP address format
console.log('\n3. Validating API URL format:');
if (apiUrl.startsWith('http://') && apiUrl.includes(':8000')) {
  console.log('   ✅ API URL format looks correct');
  
  // Extract IP address
  const ipMatch = apiUrl.match(/http:\/\/([^:]+):8000/);
  if (ipMatch && ipMatch[1]) {
    const ip = ipMatch[1];
    if (ip === 'localhost' || ip === '127.0.0.1') {
      console.log('   ⚠️  Warning: Using localhost/127.0.0.1');
      console.log('   ℹ️  For mobile devices, use your machine\'s LAN IP instead');
    } else {
      console.log(`   ✅ Using LAN IP: ${ip}`);
    }
  }
} else {
  console.log('   ❌ API URL format may be incorrect');
  console.log('   ℹ️  Should be in format: http://YOUR_LAN_IP:8000');
}

console.log('\n4. Next steps to test connectivity:');
console.log('   1. Ensure backend is running: make dev');
console.log('   2. Test API access from mobile browser:');
console.log(`      Open mobile browser and go to: ${apiUrl}/healthz`);
console.log('   3. You should see a health check response');
console.log('   4. If that works, the Expo app should connect successfully');

console.log('\n5. If you still have connection issues:');
console.log('   - Check Windows Firewall settings for port 8000');
console.log('   - Verify your LAN IP is correct');
console.log('   - Try using ngrok as an alternative');
console.log('   - Refer to DEVELOPMENT_SETUP.md for detailed instructions');