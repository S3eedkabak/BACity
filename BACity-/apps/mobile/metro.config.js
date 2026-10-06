const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');
const config = getDefaultConfig(__dirname);
config.resolver.assetExts.push('riv', 'wasm');

// Iconoir 7.10.1 supports RN 0.74, but its `module` field names an absent .js
// file (the ESM file is .mjs). Resolve ONLY this package through its valid
// official CommonJS export. Leave Expo's resolution for all other packages alone.
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === 'iconoir-react-native') {
    return { type: 'sourceFile', filePath: require.resolve('iconoir-react-native') };
  }
  const icon = /^iconoir-react-native\/(regular|solid)\/([A-Za-z0-9]+)$/.exec(moduleName);
  if (icon) {
    return { type: 'sourceFile', filePath: path.join(path.dirname(require.resolve('iconoir-react-native')), icon[1], `${icon[2]}.js`) };
  }
  return context.resolveRequest(context, moduleName, platform);
};
module.exports = config;
