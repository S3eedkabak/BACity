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
  container: { paddingVertical: 48, alignItems: "center" },
});