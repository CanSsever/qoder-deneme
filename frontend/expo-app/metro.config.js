const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

// Get the default Expo Metro configuration
const config = getDefaultConfig(__dirname);

// Define paths for the SDK
const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, '../..');
const sdkPath = path.resolve(projectRoot, '../oneshot-sdk');

// Configure Metro to resolve the local SDK package
config.watchFolders = [
  projectRoot,
  sdkPath,
];

// Configure module resolution to map 'oneshot-sdk' to its physical location
config.resolver = {
  ...config.resolver,
  
  // Add extra node modules mapping for the SDK
  extraNodeModules: {
    'oneshot-sdk': sdkPath,
  },
  
  // Add node modules paths to include the SDK's parent directory
  nodeModulesPaths: [
    path.resolve(projectRoot, 'node_modules'),
    path.resolve(sdkPath, 'node_modules'),
  ],
};

// Ensure Metro watches for changes in the SDK
config.server = {
  ...config.server,
  enhanceMiddleware: (middleware) => {
    return (req, res, next) => {
      // Log SDK resolution for debugging
      if (req.url && req.url.includes('oneshot-sdk')) {
        console.log('[Metro] Resolving oneshot-sdk:', req.url);
      }
      return middleware(req, res, next);
    };
  },
};

module.exports = config;
