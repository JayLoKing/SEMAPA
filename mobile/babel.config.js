module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    // SDK 54: react-native-reanimated v4 plugin se inyecta vía preset.
  };
};
