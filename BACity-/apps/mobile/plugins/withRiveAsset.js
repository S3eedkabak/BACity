const { withDangerousMod, withXcodeProject, IOSConfig } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');
// Legacy runtime 8 supports the existing SDK34 toolchain. Its resourceName API
// reads native bundled resources (NOT Expo cache file URLs). No runtime download.
function copyResource(projectRoot, directory) {
  fs.mkdirSync(directory, { recursive: true });
  fs.copyFileSync(path.join(projectRoot, 'assets/rive/walk-cycle.riv'), path.join(directory, 'bacity_walk.riv'));
}
module.exports = function withRiveAsset(config) {
  config = withDangerousMod(config, ['android', async value => {
    copyResource(value.modRequest.projectRoot, path.join(value.modRequest.platformProjectRoot, 'app/src/main/res/raw'));
    return value;
  }]);
  return withXcodeProject(config, value => {
    copyResource(value.modRequest.projectRoot, path.join(value.modRequest.platformProjectRoot, 'BACityRive'));
    IOSConfig.XcodeUtils.ensureGroupRecursively(value.modResults, 'Resources');
    IOSConfig.XcodeUtils.addResourceFileToGroup({ filepath: 'BACityRive/bacity_walk.riv', groupName: 'Resources', project: value.modResults, isBuildFile: true });
    return value;
  });
};
module.exports.copyResource = copyResource;
