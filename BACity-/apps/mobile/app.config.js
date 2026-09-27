module.exports = ({ config }) => {
  const resolved = { ...config, plugins: [...(config.plugins || [])] };
  const iosUrlScheme = process.env.EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME;
  if (iosUrlScheme) {
    resolved.plugins.push(["@react-native-google-signin/google-signin", { iosUrlScheme }]);
  }
  return resolved;
};
