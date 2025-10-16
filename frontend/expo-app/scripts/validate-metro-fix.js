#!/usr/bin/env node

/**
 * Implementation Validation Script
 * 
 * This script validates that the Metro SDK resolution fix has been
 * properly implemented by checking all required files and configurations.
 */

const fs = require('fs');
const path = require('path');

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

function logHeader(message) {
  log(`\n${'═'.repeat(60)}`, colors.bright);
  log(`  ${message}`, colors.bright);
  log(`${'═'.repeat(60)}\n`, colors.bright);
}

const projectRoot = path.resolve(__dirname, '..');
const sdkRoot = path.resolve(projectRoot, '../oneshot-sdk');

let checksPassed = 0;
let checksFailed = 0;
let warnings = 0;

logHeader('Metro SDK Resolution Fix - Implementation Validation');

// Check 1: Metro configuration file
logInfo('Check 1: Metro configuration file...');
const metroConfigPath = path.resolve(projectRoot, 'metro.config.js');
if (fs.existsSync(metroConfigPath)) {
  const metroConfig = fs.readFileSync(metroConfigPath, 'utf8');
  
  if (metroConfig.includes('watchFolders')) {
    logSuccess('metro.config.js exists and contains watchFolders');
    checksPassed++;
  } else {
    logError('metro.config.js exists but missing watchFolders configuration');
    checksFailed++;
  }
  
  if (metroConfig.includes('extraNodeModules')) {
    logSuccess('metro.config.js contains extraNodeModules configuration');
    checksPassed++;
  } else {
    logError('metro.config.js missing extraNodeModules configuration');
    checksFailed++;
  }
} else {
  logError('metro.config.js not found');
  checksFailed += 2;
}

// Check 2: SDK verification script
logInfo('\nCheck 2: SDK verification script...');
const verifySdkPath = path.resolve(projectRoot, 'scripts/verify-sdk.js');
if (fs.existsSync(verifySdkPath)) {
  const stat = fs.statSync(verifySdkPath);
  if (stat.mode & fs.constants.S_IXUSR) {
    logSuccess('verify-sdk.js exists and is executable');
  } else {
    logWarning('verify-sdk.js exists but may not be executable');
    warnings++;
  }
  checksPassed++;
} else {
  logError('verify-sdk.js not found');
  checksFailed++;
}

// Check 3: Setup development script
logInfo('\nCheck 3: Setup development script...');
const setupDevPath = path.resolve(projectRoot, 'scripts/setup-dev.js');
if (fs.existsSync(setupDevPath)) {
  const stat = fs.statSync(setupDevPath);
  if (stat.mode & fs.constants.S_IXUSR) {
    logSuccess('setup-dev.js exists and is executable');
  } else {
    logWarning('setup-dev.js exists but may not be executable');
    warnings++;
  }
  checksPassed++;
} else {
  logError('setup-dev.js not found');
  checksFailed++;
}

// Check 4: Package.json scripts
logInfo('\nCheck 4: Package.json scripts...');
const packageJsonPath = path.resolve(projectRoot, 'package.json');
if (fs.existsSync(packageJsonPath)) {
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
  
  const requiredScripts = [
    'verify:sdk',
    'setup:dev',
    'dev:tunnel',
    'dev:lan',
    'build:sdk',
  ];
  
  const missingScripts = requiredScripts.filter(script => !packageJson.scripts[script]);
  
  if (missingScripts.length === 0) {
    logSuccess('All required scripts are present in package.json');
    checksPassed++;
  } else {
    logError(`Missing scripts in package.json: ${missingScripts.join(', ')}`);
    checksFailed++;
  }
  
  if (packageJson.scripts.prestart && packageJson.scripts.prestart.includes('verify-sdk')) {
    logSuccess('prestart script includes SDK verification');
    checksPassed++;
  } else {
    logWarning('prestart script may not include SDK verification');
    warnings++;
  }
} else {
  logError('package.json not found');
  checksFailed += 2;
}

// Check 5: SDK structure
logInfo('\nCheck 5: SDK package structure...');
if (fs.existsSync(sdkRoot)) {
  logSuccess('SDK directory exists');
  checksPassed++;
  
  const sdkPackageJsonPath = path.resolve(sdkRoot, 'package.json');
  if (fs.existsSync(sdkPackageJsonPath)) {
    const sdkPackageJson = JSON.parse(fs.readFileSync(sdkPackageJsonPath, 'utf8'));
    
    if (sdkPackageJson.main === 'dist/index.js') {
      logSuccess('SDK package.json has correct main field');
      checksPassed++;
    } else {
      logError(`SDK package.json main field is incorrect: ${sdkPackageJson.main}`);
      checksFailed++;
    }
    
    if (sdkPackageJson.types === 'dist/index.d.ts') {
      logSuccess('SDK package.json has correct types field');
      checksPassed++;
    } else {
      logError(`SDK package.json types field is incorrect: ${sdkPackageJson.types}`);
      checksFailed++;
    }
  } else {
    logError('SDK package.json not found');
    checksFailed += 2;
  }
  
  const sdkSrcPath = path.resolve(sdkRoot, 'src');
  if (fs.existsSync(sdkSrcPath)) {
    logSuccess('SDK source directory exists');
    checksPassed++;
  } else {
    logError('SDK source directory not found');
    checksFailed++;
  }
  
  const sdkTsconfigPath = path.resolve(sdkRoot, 'tsconfig.json');
  if (fs.existsSync(sdkTsconfigPath)) {
    logSuccess('SDK tsconfig.json exists');
    checksPassed++;
  } else {
    logError('SDK tsconfig.json not found');
    checksFailed++;
  }
} else {
  logError('SDK directory not found');
  checksFailed += 5;
}

// Check 6: Documentation
logInfo('\nCheck 6: Documentation files...');
const docs = [
  { path: 'METRO_SDK_RESOLUTION_FIX.md', name: 'Comprehensive documentation' },
  { path: 'QUICK_START_METRO_FIX.md', name: 'Quick start guide' },
];

docs.forEach(doc => {
  const docPath = path.resolve(projectRoot, doc.path);
  if (fs.existsSync(docPath)) {
    logSuccess(`${doc.name} exists`);
    checksPassed++;
  } else {
    logWarning(`${doc.name} not found`);
    warnings++;
  }
});

// Check 7: Expo app dependency
logInfo('\nCheck 7: SDK dependency in Expo app...');
const expoPackageJsonPath = path.resolve(projectRoot, 'package.json');
if (fs.existsSync(expoPackageJsonPath)) {
  const expoPackageJson = JSON.parse(fs.readFileSync(expoPackageJsonPath, 'utf8'));
  
  if (expoPackageJson.dependencies['oneshot-sdk']) {
    const sdkDep = expoPackageJson.dependencies['oneshot-sdk'];
    if (sdkDep.startsWith('file:')) {
      logSuccess(`SDK is linked as local dependency: ${sdkDep}`);
      checksPassed++;
    } else {
      logWarning(`SDK dependency is not a file reference: ${sdkDep}`);
      warnings++;
    }
  } else {
    logError('oneshot-sdk dependency not found in package.json');
    checksFailed++;
  }
}

// Final summary
logHeader('Validation Summary');

const total = checksPassed + checksFailed;
const percentage = total > 0 ? ((checksPassed / total) * 100).toFixed(1) : 0;

log(`Total Checks: ${total}`, colors.blue);
log(`Passed: ${checksPassed}`, colors.green);
log(`Failed: ${checksFailed}`, checksFailed > 0 ? colors.red : colors.green);
log(`Warnings: ${warnings}`, warnings > 0 ? colors.yellow : colors.green);
log(`Success Rate: ${percentage}%\n`, percentage >= 90 ? colors.green : colors.yellow);

if (checksFailed === 0) {
  logHeader('✓ Implementation Validated Successfully!');
  log('The Metro SDK resolution fix has been properly implemented.', colors.green);
  log('You can now run:', colors.green);
  log('  npm run setup:dev    - To set up the development environment', colors.green);
  log('  npm run dev:tunnel   - To start Expo in tunnel mode', colors.green);
  log('  npm run dev:lan      - To start Expo in LAN mode', colors.green);
  log('  npm run dev          - To start Expo in local mode\n', colors.green);
  process.exit(0);
} else {
  logHeader('✗ Implementation Validation Failed');
  log(`${checksFailed} critical check(s) failed.`, colors.red);
  log('Please review the errors above and fix the issues.\n', colors.red);
  process.exit(1);
}
