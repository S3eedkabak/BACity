import { ActivityIndicator, StyleSheet, View } from "react-native";
import { colors } from "../theme/colors";

export function LoadingState() {
  return (
    <View style={styles.container}>
      <ActivityIndicator color={colors.primary} size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    minHeight: 180,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
});
