# Metro SDK Resolution - Solution Architecture

## Complete Solution Flow

### Module Resolution Flow

```mermaid
graph TB
    A[Developer runs npm run dev:tunnel] --> B[prestart hook executes]
    B --> C[verify-sdk.js runs]
    C --> D{SDK dist/ exists?}
    D -->|No| E[Auto-build SDK]
    D -->|Yes| F{All artifacts present?}
    E --> G[npm install in SDK]
    G --> H[npm run build in SDK]
    H --> F
    F -->|Yes| I[Verification passed]
    F -->|No| E
    I --> J[check-api.js runs]
    J --> K[Metro bundler starts]
    K --> L[expo start --tunnel]
    L --> M[App imports oneshot-sdk]
    M --> N[Metro resolves via metro.config.js]
    N --> O{extraNodeModules mapping}
    O --> P[Resolve to ../oneshot-sdk]
    P --> Q[Load dist/index.js]
    Q --> R[Bundle app successfully]
    R --> S[App runs on device]
```

### Metro Configuration Architecture

```mermaid
graph LR
    A[Import Statement] -->|"import { X } from 'oneshot-sdk'"| B[Metro Resolver]
    B --> C{Check extraNodeModules}
    C -->|Found: oneshot-sdk| D[Map to sdkPath]
    D --> E[../oneshot-sdk]
    E --> F{Check package.json}
    F --> G[main: dist/index.js]
    G --> H[Load compiled JS]
    H --> I{watchFolders monitoring}
    I -->|File changes| J[Hot reload]
    I -->|No changes| K[Use cached bundle]
```

### File Structure

```
qoder-deneme/
├── frontend/
│   ├── expo-app/
│   │   ├── metro.config.js ────────────┐
│   │   │   • watchFolders              │
│   │   │   • extraNodeModules          │
│   │   │   • nodeModulesPaths          │
│   │   │                               │
│   │   ├── package.json                │
│   │   │   • "oneshot-sdk": "file:../" │
│   │   │   • Scripts for SDK mgmt      │
│   │   │                               │
│   │   ├── scripts/                    │
│   │   │   ├── verify-sdk.js ──────────┼─── Verifies SDK build
│   │   │   ├── setup-dev.js ───────────┼─── Initial setup
│   │   │   └── validate-metro-fix.js ──┼─── Validates implementation
│   │   │                               │
│   │   └── src/                        │
│   │       └── screens/                │
│   │           └── LoginScreen.tsx ────┼─── Imports from oneshot-sdk
│   │                                   │
│   └── oneshot-sdk/ ◄──────────────────┘
│       ├── package.json
│       │   • main: dist/index.js
│       │   • types: dist/index.d.ts
│       │
│       ├── src/                   (TypeScript source)
│       │   ├── index.ts
│       │   ├── client.ts
│       │   └── types.ts
│       │
│       └── dist/                  (Compiled JavaScript)
│           ├── index.js           ◄─── Metro loads this
│           ├── index.d.ts         ◄─── TypeScript uses this
│           └── ...
```

### Development Workflow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Script as verify-sdk.js
    participant SDK as oneshot-sdk
    participant Metro as Metro Bundler
    participant App as Expo App
    
    Dev->>Script: npm run dev:tunnel
    Script->>SDK: Check dist/ directory
    
    alt SDK not built
        Script->>SDK: npm install
        Script->>SDK: npm run build
        SDK-->>Script: Build complete
    end
    
    Script->>Metro: Start Metro bundler
    Metro->>Metro: Load metro.config.js
    Metro->>Metro: Configure watchFolders
    Metro->>Metro: Set extraNodeModules
    
    App->>Metro: import from 'oneshot-sdk'
    Metro->>SDK: Resolve via extraNodeModules
    SDK-->>Metro: Return dist/index.js
    Metro->>App: Bundle with SDK code
    App-->>Dev: App running successfully
```

### SDK Build Process

```mermaid
graph TD
    A[TypeScript Source Files] --> B[src/index.ts]
    A --> C[src/client.ts]
    A --> D[src/types.ts]
    A --> E[src/*.ts]
    
    B --> F[TypeScript Compiler tsc]
    C --> F
    D --> F
    E --> F
    
    F --> G[Compiled JavaScript]
    G --> H[dist/index.js]
    G --> I[dist/client.js]
    G --> J[dist/types.js]
    G --> K[dist/*.js]
    
    F --> L[Type Definitions]
    L --> M[dist/index.d.ts]
    L --> N[dist/client.d.ts]
    L --> O[dist/types.d.ts]
    L --> P[dist/*.d.ts]
    
    H --> Q[Metro loads for bundling]
    M --> R[TypeScript uses for type checking]
```

### Script Execution Flow

```mermaid
graph TB
    Start[npm start or npm run dev:*] --> PreStart[prestart hook]
    PreStart --> Verify[verify-sdk.js]
    
    Verify --> Check1{SDK dir exists?}
    Check1 -->|No| Error1[Error: SDK not found]
    Check1 -->|Yes| Check2{package.json valid?}
    
    Check2 -->|No| Error2[Error: Invalid package.json]
    Check2 -->|Yes| Check3{dist/ exists?}
    
    Check3 -->|No & Auto-build ON| Build1[Build SDK]
    Check3 -->|No & Auto-build OFF| Error3[Error: SDK not built]
    Check3 -->|Yes| Check4{All artifacts present?}
    
    Build1 --> Check4
    
    Check4 -->|No| Build2[Rebuild SDK]
    Check4 -->|Yes| Check5{Strict mode?}
    
    Build2 --> Check5
    
    Check5 -->|Yes| Check6{Build current?}
    Check5 -->|No| Success[Verification passed]
    
    Check6 -->|No| Build3[Rebuild SDK]
    Check6 -->|Yes| Success
    
    Build3 --> Success
    
    Success --> CheckAPI[check-api.js]
    CheckAPI --> StartMetro[Start Metro bundler]
    StartMetro --> RunApp[Run Expo app]
```

## Key Components

### 1. Metro Config (metro.config.js)

**Purpose**: Configure Metro to resolve local SDK package

**Key Settings**:
- `watchFolders`: Monitor both app and SDK directories
- `extraNodeModules`: Map package name to physical location
- `nodeModulesPaths`: Additional resolution paths

### 2. Verification Script (verify-sdk.js)

**Purpose**: Ensure SDK is built before running app

**Checks**:
- ✓ SDK directory exists
- ✓ package.json is valid
- ✓ Build artifacts exist
- ✓ All required files present
- ✓ Build is current (optional)

**Actions**:
- Auto-build if needed
- Comprehensive error reporting
- Environment variable configuration

### 3. Setup Script (setup-dev.js)

**Purpose**: One-time development environment setup

**Steps**:
1. Verify SDK exists
2. Install SDK dependencies
3. Build SDK
4. Verify build
5. Install Expo dependencies
6. Verify Metro config

### 4. Validation Script (validate-metro-fix.js)

**Purpose**: Validate implementation completeness

**Checks**:
- Metro config exists and is correct
- All scripts present and executable
- Package.json updated correctly
- SDK structure is valid
- Documentation files exist

## Resolution Comparison

### Before Fix

```
Developer: npm run dev:tunnel
Metro: Starting bundler...
Metro: Resolving 'oneshot-sdk'...
Metro: ✗ Unable to resolve module 'oneshot-sdk'
Metro: ✗ Module not found in node_modules
App: ✗ Failed to load
```

### After Fix

```
Developer: npm run dev:tunnel
verify-sdk: Checking SDK build...
verify-sdk: ✓ SDK directory found
verify-sdk: ✓ Build artifacts present
verify-sdk: ✓ Verification passed
Metro: Starting bundler...
Metro: Loading metro.config.js
Metro: Configuring watchFolders
Metro: Setting extraNodeModules
Metro: Resolving 'oneshot-sdk'...
Metro: ✓ Resolved to ../oneshot-sdk
Metro: ✓ Loaded dist/index.js
App: ✓ Running successfully
```

## Environment Variables

```bash
# Disable automatic SDK building
export SDK_AUTO_BUILD=false

# Enable strict timestamp checking
export SDK_STRICT_MODE=true

# Run with custom settings
npm run dev:tunnel
```

## Troubleshooting Decision Tree

```mermaid
graph TD
    Issue[Module Resolution Error] --> Q1{Metro running?}
    Q1 -->|No| Start[npm run dev:tunnel]
    Q1 -->|Yes| Q2{Cache issue?}
    
    Q2 -->|Maybe| Clear[npm run reset:metro]
    Q2 -->|No| Q3{SDK built?}
    
    Q3 -->|No| Build[npm run build:sdk]
    Q3 -->|Yes| Q4{Metro config exists?}
    
    Q4 -->|No| Setup[npm run setup:dev]
    Q4 -->|Yes| Q5{Config correct?}
    
    Q5 -->|No| Validate[npm run validate:metro-fix]
    Q5 -->|Yes| Q6{SDK in node_modules?}
    
    Q6 -->|No| Install[npm install]
    Q6 -->|Yes| Deep[Check detailed logs]
```

## Success Indicators

### Verification Success
```
✓ SDK directory found
✓ SDK package.json is valid
✓ Main entry point: dist/index.js
✓ Type definitions: dist/index.d.ts
✓ SDK dist/ directory found
✓ Main entry file exists
✓ Type definitions exists
✓ Build is up to date
✓ SDK Verification Passed
```

### Metro Resolution Success
```
[Metro] Loading metro.config.js
[Metro] Configured watchFolders
[Metro] Set extraNodeModules for 'oneshot-sdk'
[Metro] Resolving oneshot-sdk: .../bundle?...
[Metro] Bundle loaded successfully
```

### App Import Success
```typescript
import { OneShotClient, ConnectionStatus } from 'oneshot-sdk';
// ✓ No errors
// ✓ Types available
// ✓ Auto-completion works
```

## Performance Metrics

- **Initial Setup**: ~30-60 seconds (one-time)
- **SDK Build**: ~5-10 seconds (cached)
- **Verification**: ~1-2 seconds (per start)
- **Metro Start**: Normal (no overhead)
- **Hot Reload**: Normal (no impact)

## Security Flow

```mermaid
graph LR
    A[Local Source Code] --> B[TypeScript Compiler]
    B --> C[Local dist/ directory]
    C --> D[Metro Bundler]
    D --> E[App Bundle]
    E --> F[Device/Emulator]
    
    Note1[No network requests] -.-> B
    Note2[No external packages] -.-> C
    Note3[Local only] -.-> D
```

## Platform Compatibility

```
┌──────────────┬──────────┬──────────┬──────────┐
│   Platform   │  Tunnel  │   LAN    │  Local   │
├──────────────┼──────────┼──────────┼──────────┤
│    Linux     │    ✓     │    ✓     │    ✓     │
│    macOS     │    ✓     │    ✓     │    ✓     │
│   Windows    │    ✓     │    ✓     │    ✓     │
└──────────────┴──────────┴──────────┴──────────┘
```

---

**Complete solution architecture for Metro SDK resolution in Expo tunnel mode.**
