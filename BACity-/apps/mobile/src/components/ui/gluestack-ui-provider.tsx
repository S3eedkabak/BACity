import React, { useEffect } from "react";
import { Appearance, ColorSchemeName, View, ViewProps } from "react-native";
import { OverlayProvider } from "@gluestack-ui/core/overlay/creator";
import { ToastProvider } from "@gluestack-ui/core/toast/creator";

export type ModeType = "light" | "dark" | "system";

export function GluestackUIProvider({
  mode = "light",
  ...props
}: {
  mode?: ModeType;
  children?: React.ReactNode;
  style?: ViewProps["style"];
}) {
  useEffect(() => {
    Appearance.setColorScheme(mode as ColorSchemeName);
  }, [mode]);

  return (
    <View style={[{ flex: 1, height: "100%", width: "100%" }, props.style]}>
      <OverlayProvider>
        <ToastProvider>{props.children}</ToastProvider>
      </OverlayProvider>
    </View>
  );
}
