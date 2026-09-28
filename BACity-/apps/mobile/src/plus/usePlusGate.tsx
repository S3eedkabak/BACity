import { ReactNode, useCallback } from "react";
import { router } from "expo-router";
import { useEntitlements } from "../hooks/useEntitlements";
import { PlusFeature, plusPaywallRoute, resolvePlusGate } from "./policy";

export function usePlusGate() {
  const entitlements = useEntitlements();
  const decision = resolvePlusGate({
    authenticated: entitlements.authenticated,
    pending: entitlements.authenticated && entitlements.isPending,
    failed: entitlements.isError,
    active: entitlements.plus?.active === true,
  });

  const run = useCallback((feature: PlusFeature, onAllowed: () => void) => {
    if (decision === "allow") onAllowed();
    else if (decision === "paywall" || decision === "error") {
      router.push(plusPaywallRoute(feature, decision === "error"));
    }
  }, [decision]);

  return { decision, run, refresh: entitlements.refresh };
}

export function PlusGateAction({
  feature,
  onAllowed,
  children,
}: {
  feature: PlusFeature;
  onAllowed: () => void;
  children: (props: { onPress: () => void; loading: boolean }) => ReactNode;
}) {
  const gate = usePlusGate();
  return <>{children({ onPress: () => gate.run(feature, onAllowed), loading: gate.decision === "loading" })}</>;
}
