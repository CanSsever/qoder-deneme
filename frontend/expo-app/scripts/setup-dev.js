#!/usr/bin/env node

/**
 * Development Environment Setup Script
 * 
 * This script sets up the development environment for the Expo app
 * by ensuring all dependencies are properly installed and configured.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
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

logHeader('OneShot Expo App - Development Setup');

// Step 1: Verify SDK exists
logInfo('Step 1: Verifying SDK directory...');
if (!fs.existsSync(sdkRoot)) {
  logError(`SDK directory not found at: ${sdkRoot}`);
  logError('Please ensure the oneshot-sdk package is in the correct location.');
  process.exit(1);
}
logSuccess('SDK directory found');

// Step 2: Install SDK dependencies
logInfo('\nStep 2: Installing SDK dependencies...');
try {
  execSync('npm install', {
    cwd: sdkRoot,
    stdio: 'inherit',
  });
  logSuccess('SDK dependencies installed');
} catch (error) {
  logError(`Failed to install SDK dependencies: ${error.message}`);
  process.exit(1);
}

// Step 3: Build SDK
logInfo('\nStep 3: Building SDK...');
try {
  execSync('npm run build', {
    cwd: sdkRoot,
    stdio: 'inherit',
  });
  logSuccess('SDK build completed');
} catch (error) {
  logError(`Failed to build SDK: ${error.message}`);
  process.exit(1);
}

// Step 4: Verify SDK build
logInfo('\nStep 4: Verifying SDK build...');
const distPath = path.resolve(sdkRoot, 'dist');
const indexJsPath = path.resolve(distPath, 'index.js');
const indexDtsPath = path.resolve(distPath, 'index.d.ts');

if (!fs.existsSync(distPath)) {
  logError('SDK dist directory was not created');
  process.exit(1);
}

if (!fs.existsSync(indexJsPath)) {
  logError('SDK index.js was not created');
  process.exit(1);
}

if (!fs.existsSync(indexDtsPath)) {
  logError('SDK type definitions were not created');
  process.exit(1);
}

logSuccess('SDK build verified successfully');

// Step 5: Install Expo app dependencies
logInfo('\nStep 5: Installing Expo app dependencies...');
try {
  execSync('npm install', {
    cwd: projectRoot,
    stdio: 'inherit',
  });
  logSuccess('Expo app dependencies installed');
} catch (error) {
  logError(`Failed to install Expo app dependencies: ${error.message}`);
  process.exit(1);
}

// Step 6: Verify Metro configuration
logInfo('\nStep 6: Verifying Metro configuration...');
const metroConfigPath = path.resolve(projectRoot, 'metro.config.js');
if (!fs.existsSync(metroConfigPath)) {
  logError('metro.config.js not found');
  logError('This file is required for proper SDK resolution');
  process.exit(1);
}
logSuccess('Metro configuration found');

// Final summary
logHeader('Setup Complete!');

log('Your development environment is ready. You can now:', colors.green);
log('', colors.green);
log('  • Run in tunnel mode:  npm run dev:tunnel', colors.green);
log('  • Run in LAN mode:     npm run dev:lan', colors.green);
log('  • Run in local mode:   npm run dev', colors.green);
log('', colors.green);
log('  • Build SDK only:      npm run build:sdk', colors.green);
log('  • Verify SDK only:     npm run verify:sdk', colors.green);
log('', colors.green);

log('\nHappy coding! 🚀\n', colors.magenta);
