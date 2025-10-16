# Metro SDK Resolution Fix - Deployment Checklist

## ✅ Pre-Deployment Verification

Use this checklist to ensure the Metro SDK resolution fix is properly deployed and working.

---

## 1. Installation & Setup

### First-Time Setup (Run Once)

```bash
cd frontend/expo-app
npm run setup:dev
```

**Expected Output**:
```
✓ SDK directory found
✓ SDK dependencies installed
✓ SDK build completed
✓ SDK build verified successfully
✓ Expo app dependencies installed
✓ Metro configuration found
✓ Setup Complete!
```

**Checklist**:
- [ ] No errors during setup
- [ ] SDK `dist/` directory created
- [ ] `dist/index.js` exists
- [ ] `dist/index.d.ts` exists
- [ ] Metro config exists
- [ ] All dependencies installed

---

## 2. Validate Implementation

### Run Validation Script

```bash
npm run validate:metro-fix
```

**Expected Output**:
```
✓ metro.config.js exists and contains watchFolders
✓ metro.config.js contains extraNodeModules configuration
✓ verify-sdk.js exists and is executable
✓ setup-dev.js exists and is executable
✓ All required scripts are present
✓ Implementation Validated Successfully!
```

**Checklist**:
- [ ] All checks passed
- [ ] No failed checks
- [ ] Success rate: 100%

---

## 3. Verify SDK Build

### Check SDK Status

```bash
npm run verify:sdk
```

**Expected Output**:
```
✓ SDK directory found
✓ SDK package.json is valid
✓ Main entry point: dist/index.js
✓ Type definitions: dist/index.d.ts
✓ SDK dist/ directory found
✓ Main entry file exists
✓ Type definitions exists
✓ SDK Verification Passed
```

**Checklist**:
- [ ] SDK verification passed
- [ ] No build errors
- [ ] All artifacts present

---

## 4. Test Development Modes

### Test Local Mode

```bash
npm run dev
```

**Expected**:
- [ ] Metro starts without errors
- [ ] No "Unable to resolve" errors
- [ ] QR code displayed
- [ ] App loads on device/emulator

### Test LAN Mode

```bash
npm run dev:lan
```

**Expected**:
- [ ] Metro starts in LAN mode
- [ ] SDK resolves correctly
- [ ] App accessible on local network
- [ ] No module resolution errors

### Test Tunnel Mode

```bash
npm run dev:tunnel
```

**Expected**:
- [ ] Metro starts in tunnel mode
- [ ] Expo tunnel URL displayed
- [ ] SDK imports work correctly
- [ ] App accessible remotely

---

## 5. Verify SDK Imports

### Test in LoginScreen.tsx (or any component)

```typescript
import { OneShotClient, ConnectionStatus } from 'oneshot-sdk';

// Should work without errors
const client = new OneShotClient({
  baseURL: 'http://localhost:3000',
  apiKey: 'test-key',
});

console.log('ConnectionStatus:', ConnectionStatus);
```

**Checklist**:
- [ ] Import statement works
- [ ] No TypeScript errors
- [ ] Auto-completion available
- [ ] Types recognized
- [ ] Runtime code works

---

## 6. File Structure Verification

### Check Required Files Exist

```bash
# Metro config
ls -l metro.config.js

# Scripts
ls -l scripts/verify-sdk.js
ls -l scripts/setup-dev.js
ls -l scripts/validate-metro-fix.js

# Documentation
ls -l METRO_SDK_RESOLUTION_FIX.md
ls -l QUICK_START_METRO_FIX.md
```

**Checklist**:
- [ ] `metro.config.js` exists
- [ ] `scripts/verify-sdk.js` exists (executable)
- [ ] `scripts/setup-dev.js` exists (executable)
- [ ] `scripts/validate-metro-fix.js` exists (executable)
- [ ] Documentation files exist

---

## 7. Package.json Scripts Verification

### Check New Scripts Present

```bash
npm run --list | grep -E "(verify:sdk|setup:dev|dev:tunnel|dev:lan|build:sdk)"
```

**Expected Scripts**:
- [ ] `verify:sdk`
- [ ] `setup:dev`
- [ ] `validate:metro-fix`
- [ ] `dev:tunnel`
- [ ] `dev:lan`
- [ ] `build:sdk`

---

## 8. Metro Configuration Check

### Verify Metro Config Content

```bash
cat metro.config.js | grep -E "(watchFolders|extraNodeModules|oneshot-sdk)"
```

**Expected Content**:
- [ ] `watchFolders` array with projectRoot and sdkPath
- [ ] `extraNodeModules` with 'oneshot-sdk' mapping
- [ ] `nodeModulesPaths` configured

---

## 9. SDK Structure Verification

### Check SDK Files

```bash
# Navigate to SDK
cd ../oneshot-sdk

# Check structure
ls -la package.json tsconfig.json
ls -la src/
ls -la dist/
```

**Checklist**:
- [ ] `package.json` exists with `main: dist/index.js`
- [ ] `tsconfig.json` exists
- [ ] `src/` directory has TypeScript files
- [ ] `dist/` directory has compiled JS files
- [ ] `dist/index.js` exists
- [ ] `dist/index.d.ts` exists

---

## 10. Clear Cache Test

### Test Metro Cache Clearing

```bash
npm run reset:metro
```

**Expected**:
- [ ] Metro starts with cleared cache
- [ ] SDK still resolves correctly
- [ ] No errors after cache clear

---

## 11. Hot Reload Test

### Test Hot Reload Functionality

1. Start Expo: `npm run dev:tunnel`
2. Make a change to app component
3. Save file

**Expected**:
- [ ] App reloads automatically
- [ ] Changes appear on device
- [ ] No module resolution errors
- [ ] SDK imports still work

---

## 12. Build After SDK Changes

### Test SDK Rebuild Workflow

```bash
# Make a change to SDK source
cd ../oneshot-sdk
# Edit src/client.ts or any file

# Build SDK
npm run build

# Return to Expo app
cd ../expo-app

# Metro should auto-reload
```

**Expected**:
- [ ] SDK rebuilds successfully
- [ ] Metro detects changes
- [ ] App reloads with new SDK code

---

## 13. Error Handling Test

### Test Error Scenarios

#### Scenario 1: SDK Not Built

```bash
# Remove dist directory
cd ../oneshot-sdk
rm -rf dist/

# Try to start Expo
cd ../expo-app
npm run dev:tunnel
```

**Expected**:
- [ ] `verify-sdk.js` detects missing dist/
- [ ] Automatically rebuilds SDK (if auto-build enabled)
- [ ] OR shows clear error message
- [ ] Metro starts successfully after build

#### Scenario 2: Missing Metro Config

```bash
# Rename metro.config.js
mv metro.config.js metro.config.js.bak

# Try validation
npm run validate:metro-fix
```

**Expected**:
- [ ] Validation script detects missing config
- [ ] Clear error message shown
- [ ] Restore config: `mv metro.config.js.bak metro.config.js`

---

## 14. Cross-Platform Test (if applicable)

### Test on Different Operating Systems

**Linux**:
- [ ] Setup works
- [ ] All modes work
- [ ] SDK resolves

**macOS**:
- [ ] Setup works
- [ ] All modes work
- [ ] SDK resolves

**Windows**:
- [ ] Setup works
- [ ] All modes work
- [ ] SDK resolves

---

## 15. Documentation Review

### Verify Documentation Completeness

**Check Files**:
- [ ] `METRO_SDK_RESOLUTION_FIX.md` - Comprehensive guide exists
- [ ] `QUICK_START_METRO_FIX.md` - Quick reference exists
- [ ] `IMPLEMENTATION_COMPLETE.md` - Implementation report exists
- [ ] `SOLUTION_DIAGRAM.md` - Architecture diagrams exist

**Content Check**:
- [ ] Troubleshooting section present
- [ ] Usage examples clear
- [ ] All scripts documented
- [ ] Environment variables explained

---

## 16. Performance Check

### Measure Performance Impact

**Initial Start Time**:
- Before fix: _________
- After fix: _________
- Difference: _________ (should be minimal)

**Hot Reload Time**:
- Before fix: _________
- After fix: _________
- Difference: _________ (should be same)

**Bundle Size**:
- Before fix: _________
- After fix: _________
- Difference: _________ (should be same)

**Expected**:
- [ ] Minimal start time increase (<2s)
- [ ] Hot reload unaffected
- [ ] Bundle size unchanged

---

## 17. CI/CD Integration (if applicable)

### Continuous Integration Setup

```yaml
# Example .github/workflows/test.yml
- name: Setup SDK
  run: |
    cd frontend/oneshot-sdk
    npm install
    npm run build

- name: Setup Expo App
  run: |
    cd frontend/expo-app
    npm install

- name: Validate Implementation
  run: |
    cd frontend/expo-app
    npm run validate:metro-fix
```

**Checklist**:
- [ ] CI workflow includes SDK build
- [ ] Validation runs in CI
- [ ] All tests pass in CI

---

## 18. Production Readiness

### Final Production Checks

**Code Quality**:
- [ ] No console.log statements (except intentional)
- [ ] No TODO comments in critical code
- [ ] Error handling in place
- [ ] TypeScript errors resolved

**Configuration**:
- [ ] Metro config optimized
- [ ] Environment variables documented
- [ ] Secrets not hardcoded

**Documentation**:
- [ ] README updated
- [ ] Team trained on new scripts
- [ ] Troubleshooting guide available

---

## 19. Team Handoff

### Knowledge Transfer Checklist

**Documentation Provided**:
- [ ] Quick start guide shared
- [ ] Full documentation accessible
- [ ] Common issues documented

**Training Completed**:
- [ ] Team knows about new scripts
- [ ] Team understands SDK build process
- [ ] Team can troubleshoot common issues

**Support**:
- [ ] Contact person assigned
- [ ] Issue tracking set up
- [ ] Escalation path defined

---

## 20. Rollback Plan

### Emergency Rollback Procedure

If issues occur, rollback steps:

1. **Remove Metro Config**:
   ```bash
   mv metro.config.js metro.config.js.disabled
   ```

2. **Revert package.json**:
   ```bash
   git checkout package.json
   ```

3. **Remove Scripts**:
   ```bash
   rm scripts/verify-sdk.js scripts/setup-dev.js scripts/validate-metro-fix.js
   ```

4. **Clear Cache**:
   ```bash
   npm run reset:metro
   ```

**Rollback Checklist**:
- [ ] Rollback procedure documented
- [ ] Rollback tested in non-prod
- [ ] Team knows rollback steps

---

## Summary Checklist

### Quick Verification (All Must Pass)

- [ ] ✅ `npm run setup:dev` completes successfully
- [ ] ✅ `npm run validate:metro-fix` passes all checks
- [ ] ✅ `npm run verify:sdk` shows SDK is built
- [ ] ✅ `npm run dev:tunnel` starts without errors
- [ ] ✅ `npm run dev:lan` works correctly
- [ ] ✅ `npm run dev` (local mode) works
- [ ] ✅ SDK imports work in components
- [ ] ✅ Hot reload functions normally
- [ ] ✅ All documentation present
- [ ] ✅ Team is trained

---

## Issue Tracking

### Known Issues (None Expected)

| Issue | Status | Resolution |
|-------|--------|------------|
| - | - | - |

### Reported Issues

| Date | Issue | Reporter | Status | Resolution |
|------|-------|----------|--------|------------|
| - | - | - | - | - |

---

## Sign-Off

### Deployment Approval

**Tested By**: _________________  
**Date**: _________________  
**All Checks Passed**: [ ] Yes [ ] No  
**Ready for Production**: [ ] Yes [ ] No  

**Approved By**: _________________  
**Date**: _________________  

**Notes**:
_______________________________________________
_______________________________________________
_______________________________________________

---

## Post-Deployment Monitoring

### Week 1 Checklist

- [ ] Day 1: Monitor for errors
- [ ] Day 3: Check team feedback
- [ ] Day 7: Review performance metrics

### Week 2-4 Checklist

- [ ] Week 2: Gather user feedback
- [ ] Week 3: Optimize if needed
- [ ] Week 4: Final review and documentation update

---

**This checklist ensures complete and correct deployment of the Metro SDK resolution fix.**
