#!/usr/bin/env node

/**
 * SDK Build Verification Script
 * 
 * This script ensures that the oneshot-sdk package is properly built
 * before starting the Expo application. It performs the following checks:
 * 
 * 1. Verifies SDK dist/ directory exists
 * 2. Checks that all required build artifacts are present
 * 3. Validates package.json main/types fields
 * 4. Optionally rebuilds SDK if needed
 * 5. Compares timestamps to ensure build is current
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

function log(message, color = colors.reset) {
  console.log(`${color}${message}${colors.reset}`);
}

function logSuccess(message) {
  log(`✓ ${message}`, colors.green);
}

function logError(message) {
  log(`✗ ${message}`, colors.red);
}

function logWarning(message) {
  log(`⚠ ${message}`, colors.yellow);
}

function logInfo(message) {
  log(`ℹ ${message}`, colors.blue);
}

// Paths
const projectRoot = path.resolve(__dirname, '..');
const sdkRoot = path.resolve(projectRoot, '../oneshot-sdk');
const sdkDistPath = path.resolve(sdkRoot, 'dist');
const sdkPackageJsonPath = path.resolve(sdkRoot, 'package.json');
const sdkSrcPath = path.resolve(sdkRoot, 'src');

// Configuration
const AUTO_BUILD = process.env.SDK_AUTO_BUILD !== 'false';
const STRICT_MODE = process.env.SDK_STRICT_MODE === 'true';

log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright);
log('  OneShot SDK Build Verification', colors.bright);
log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.bright);

// Step 1: Check if SDK directory exists
logInfo('Step 1: Checking SDK directory...');
if (!fs.existsSync(sdkRoot)) {
  logError(`SDK directory not found: ${sdkRoot}`);
  process.exit(1);
}
logSuccess(`SDK directory found: ${sdkRoot}`);

// Step 2: Check if SDK package.json exists and is valid
logInfo('\nStep 2: Validating SDK package.json...');
if (!fs.existsSync(sdkPackageJsonPath)) {
  logError('SDK package.json not found');
  process.exit(1);
}

let sdkPackageJson;
try {
  sdkPackageJson = JSON.parse(fs.readFileSync(sdkPackageJsonPath, 'utf8'));
  logSuccess('SDK package.json is valid');
} catch (error) {
  logError(`Failed to parse SDK package.json: ${error.message}`);
  process.exit(1);
}

// Step 3: Verify package.json has required fields
logInfo('\nStep 3: Checking package.json fields...');
const requiredFields = ['main', 'types'];
const missingFields = requiredFields.filter(field => !sdkPackageJson[field]);

if (missingFields.length > 0) {
  logError(`Missing required fields in package.json: ${missingFields.join(', ')}`);
  process.exit(1);
}

logSuccess(`Main entry point: ${sdkPackageJson.main}`);
logSuccess(`Type definitions: ${sdkPackageJson.types}`);

// Step 4: Check if dist/ directory exists
logInfo('\nStep 4: Checking SDK build artifacts...');
const distExists = fs.existsSync(sdkDistPath);

if (!distExists) {
  logWarning('SDK dist/ directory not found');
  
  if (AUTO_BUILD) {
    logInfo('Attempting to build SDK automatically...');
    try {
      buildSDK();
      logSuccess('SDK build completed successfully');
    } catch (error) {
      logError(`Failed to build SDK: ${error.message}`);
      process.exit(1);
    }
  } else {
    logError('SDK is not built. Please run: cd ../oneshot-sdk && npm install && npm run build');
    process.exit(1);
  }
} else {
  logSuccess('SDK dist/ directory found');
}

// Step 5: Verify required build artifacts
logInfo('\nStep 5: Verifying build artifacts...');
const mainFilePath = path.resolve(sdkRoot, sdkPackageJson.main);
const typesFilePath = path.resolve(sdkRoot, sdkPackageJson.types);

const requiredArtifacts = [
  { path: mainFilePath, name: 'Main entry file (index.js)' },
  { path: typesFilePath, name: 'Type definitions (index.d.ts)' },
];

let allArtifactsExist = true;
for (const artifact of requiredArtifacts) {
  if (fs.existsSync(artifact.path)) {
    logSuccess(`${artifact.name} exists`);
  } else {
    logError(`${artifact.name} not found: ${artifact.path}`);
    allArtifactsExist = false;
  }
}

if (!allArtifactsExist) {
  if (AUTO_BUILD) {
    logInfo('Some artifacts missing. Rebuilding SDK...');
    try {
      buildSDK();
      logSuccess('SDK rebuild completed successfully');
    } catch (error) {
      logError(`Failed to rebuild SDK: ${error.message}`);
      process.exit(1);
    }
  } else {
    logError('Required build artifacts are missing');
    process.exit(1);
  }
}

// Step 6: Check if build is current (optional, in strict mode)
if (STRICT_MODE && fs.existsSync(sdkSrcPath)) {
  logInfo('\nStep 6: Checking if build is current...');
  
  const distMtime = getLatestMtime(sdkDistPath);
  const srcMtime = getLatestMtime(sdkSrcPath);
  
  if (srcMtime > distMtime) {
    logWarning('Source files are newer than build artifacts');
    
    if (AUTO_BUILD) {
      logInfo('Rebuilding SDK with latest changes...');
      try {
        buildSDK();
        logSuccess('SDK rebuild completed successfully');
      } catch (error) {
        logError(`Failed to rebuild SDK: ${error.message}`);
        process.exit(1);
      }
    } else {
      logWarning('Build may be outdated. Consider rebuilding the SDK.');
    }
  } else {
    logSuccess('Build is up to date');
  }
}

// Step 7: Final validation
logInfo('\nStep 7: Final validation...');
const finalCheck = [
  fs.existsSync(sdkDistPath),
  fs.existsSync(mainFilePath),
  fs.existsSync(typesFilePath),
].every(Boolean);

if (finalCheck) {
  log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.green);
  log('  ✓ SDK Verification Passed', colors.green);
  log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.green);
  process.exit(0);
} else {
  log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.red);
  log('  ✗ SDK Verification Failed', colors.red);
  log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.red);
  process.exit(1);
}

// Helper Functions

function buildSDK() {
  logInfo('Installing SDK dependencies...');
  try {
    execSync('npm install', { 
      cwd: sdkRoot, 
      stdio: 'inherit',
      env: { ...process.env, NODE_ENV: 'development' }
    });
  } catch (error) {
    throw new Error(`npm install failed: ${error.message}`);
  }
  
  logInfo('Building SDK...');
  try {
    execSync('npm run build', { 
      cwd: sdkRoot, 
      stdio: 'inherit',
      env: { ...process.env, NODE_ENV: 'production' }
    });
  } catch (error) {
    throw new Error(`npm run build failed: ${error.message}`);
  }
}

function getLatestMtime(dirPath) {
  let latestMtime = 0;
  
  function walk(dir) {
    const files = fs.readdirSync(dir);
    
    for (const file of files) {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);
      
      if (stat.isDirectory()) {
        if (file !== 'node_modules' && file !== '.git') {
          walk(filePath);
        }
      } else {
        const mtime = stat.mtimeMs;
        if (mtime > latestMtime) {
          latestMtime = mtime;
        }
      }
    }
  }
  
  walk(dirPath);
  return latestMtime;
}
