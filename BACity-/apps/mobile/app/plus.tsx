import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { Linking, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { dismissPlusPaywall, isPlusFeature, PLUS_FEATURES } from "../src/plus/policy";
import { createConsumerCheckout, createConsumerPortal, getConsumerBillingStatus, reconcileConsumerBilling, ConsumerBillingStatus } from "../src/api/consumerBilling";
import { billingMessage, billingReturnState, canShowWebPurchase } from "../src/billing/presentation";
import { useEntitlements } from "../src/hooks/useEntitlements";
import { useAuthStore } from "../src/store/authStore";
import { getGooglePlayBillingConfig, verifyGooglePlayPurchase, type GooglePlayBillingConfig } from "../src/api/googlePlayBilling";
import {
  configurePlayBilling, connectPlayBilling, disconnectPlayBilling, listenForPlayPurchases, loadPlayProduct,
  restorePlayPurchases, startPlayPurchase, type PlayProduct, type PlayPurchase,
} from "../src/billing/playBilling";
import { canStartPlayPurchase, playStateMessage } from "../src/billing/playPresentation";

export default function PlusPaywallScreen() {
  const params = useLocalSearchParams<{ feature?: string | string[]; unavailable?: string; billing?: string | string[] }>();
  const feature = isPlusFeature(params.feature) ? params.feature : null;
  const entitlement = useEntitlements();
  const accountId = useAuthStore(state => state.user?.id ?? null);
  const purchaseInFlight = useRef(new Set<string>());
  const alive = useRef(true);
  const sameAccount = () => alive.current && !!accountId && useAuthStore.getState().user?.id === accountId;
  const [billing, setBilling] = useState<ConsumerBillingStatus | null>(null);
  const [working, setWorking] = useState(false);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [playConfig, setPlayConfig] = useState<GooglePlayBillingConfig | null>(null);
  const [playProduct, setPlayProduct] = useState<PlayProduct | null>(null);
  const [playMessage, setPlayMessage] = useState<string | null>(null);
  const returned = billingReturnState(params.billing);
  const active = entitlement.plus?.active === true || billing?.plus_active === true || playConfig?.plus_active === true;
  const returnMessage = useMemo(() => billingMessage(returned, working, active), [returned, working, active]);
  const dismiss = () => dismissPlusPaywall(
    () => router.canGoBack(),
    () => router.back(),
    path => router.replace(path),
  );

  const loadBilling = async () => {
    if (Platform.OS !== "web" || !entitlement.authenticated) return;
    try { setBilling(await getConsumerBillingStatus()); } catch { setBillingError("Billing status is temporarily unavailable."); }
  };

  const loadPlay = async () => {
    if (Platform.OS !== "android" || !entitlement.authenticated) return;
    const config = await getGooglePlayBillingConfig();
    if (!sameAccount()) return;
    setPlayConfig(config);
    if (!config.configured || !config.product_id || !config.obfuscated_account_id) return;
    configurePlayBilling(config.product_id, config.base_plan_id, config.obfuscated_account_id);
    const connected = await connectPlayBilling();
    if (!sameAccount()) return;
    if (!connected) throw new Error("Google Play Billing is unavailable");
    const product = await loadPlayProduct(
      config.product_id, config.base_plan_id, config.obfuscated_account_id,
    );
    if (sameAccount()) setPlayProduct(product);
  };

  useEffect(() => {
    alive.current = true;
    setBilling(null);
    setPlayConfig(null);
    setPlayProduct(null);
    setBillingError(null);
    setPlayMessage(null);
    setWorking(false);
    if (accountId) void loadBilling();
    if (!accountId || Platform.OS !== "android") return;
    let listener: ReturnType<typeof listenForPlayPurchases> | null = null;
    let mounted = true;
    void (async () => {
      try {
        const config = await getGooglePlayBillingConfig();
        if (!mounted || !sameAccount()) return;
        setPlayConfig(config);
        if (!config.configured || !config.product_id || !config.obfuscated_account_id) return;
        configurePlayBilling(config.product_id, config.base_plan_id, config.obfuscated_account_id);
        listener = listenForPlayPurchases(
          purchase => { if (mounted && sameAccount()) void verifyPlayPurchase(purchase); },
          error => {
            if (!mounted) return;
            const cancelled = String(error.code).includes("CANCEL");
            setWorking(false);
            setPlayMessage(cancelled ? playStateMessage("cancelled") : "Google Play could not complete the purchase.");
          },
        );
        const connected = await connectPlayBilling();
        if (!connected) throw new Error("Google Play Billing is unavailable");
        if (!mounted || !sameAccount()) return;
        const product = await loadPlayProduct(config.product_id, config.base_plan_id, config.obfuscated_account_id);
        if (mounted) setPlayProduct(product);
      } catch {
        if (mounted) setBillingError("Google Play Billing is temporarily unavailable.");
      }
    })();
    return () => {
      alive.current = false;
      mounted = false;
      listener?.remove();
      void disconnectPlayBilling();
    };
  }, [accountId]);
  useEffect(() => {
    if (Platform.OS !== "web" || returned !== "success" || !entitlement.authenticated) return;
    let mounted = true;
    void verifySubscription(() => mounted);
    return () => { mounted = false; };
  }, [returned, entitlement.authenticated, accountId]);

  const verifySubscription = async (isMounted = () => true) => {
    setWorking(true); setBillingError(null);
    try {
      await reconcileConsumerBilling();
      await entitlement.refresh();
      if (isMounted()) await loadBilling();
    } catch {
      if (isMounted()) setBillingError("Stripe has not confirmed the subscription yet. Retry verification shortly.");
    } finally {
      if (isMounted()) setWorking(false);
    }
  };

  const openProvider = async (create: () => Promise<{ url: string }>) => {
    setWorking(true); setBillingError(null);
    try {
      const { url } = await create();
      if (Platform.OS === "web" && typeof window !== "undefined") window.location.assign(url);
    } catch (error) {
      setBillingError(error instanceof Error ? error.message : "Billing is temporarily unavailable.");
      setWorking(false);
    }
  };

  async function verifyPlayPurchase(purchase: PlayPurchase) {
    if (!sameAccount() || purchaseInFlight.current.has(purchase.purchaseToken)) return;
    purchaseInFlight.current.add(purchase.purchaseToken);
    setWorking(true); setBillingError(null); setPlayMessage(playStateMessage("verifying"));
    try {
      const result = await verifyGooglePlayPurchase(purchase.purchaseToken, purchase.productId);
      if (!sameAccount()) return;
      await entitlement.refresh();
      await loadPlay();
      if (!sameAccount()) return;
      setPlayMessage(result.active
        ? playStateMessage("verified")
        : result.subscription_status === "pending"
          ? playStateMessage("pending")
          : "Google Play did not report an active BACity+ subscription.");
    } catch {
      if (sameAccount()) setPlayMessage(playStateMessage("failed"));
    } finally {
      purchaseInFlight.current.delete(purchase.purchaseToken);
      if (sameAccount()) setWorking(false);
    }
  }

  const purchaseOnPlay = async () => {
    if (active || playConfig?.active_paid_other_provider) {
      setPlayMessage("BACity+ is already active. Manage the existing subscription before changing providers.");
      return;
    }
    setWorking(true); setPlayMessage("Opening Google Play…"); setBillingError(null);
    try { await startPlayPurchase(); }
    catch (error) {
      setWorking(false);
      const cancelled = String((error as { code?: string })?.code).includes("CANCEL");
      setPlayMessage(cancelled ? playStateMessage("cancelled") : "Google Play could not start the purchase.");
    }
  };

  const restoreOnPlay = async () => {
    setWorking(true); setBillingError(null); setPlayMessage(playStateMessage("restoring"));
    try {
      const purchases = await restorePlayPurchases();
      if (!sameAccount()) return;
      if (!purchases.length) { setPlayMessage(playStateMessage("nothing")); return; }
      let restoredActive = false;
      for (const purchase of purchases) {
        if (!sameAccount()) return;
        const result = await verifyGooglePlayPurchase(purchase.purchaseToken, purchase.productId);
        if (!sameAccount()) return;
        restoredActive ||= result.active;
      }
      await entitlement.refresh();
      await loadPlay();
      if (!sameAccount()) return;
      setPlayMessage(restoredActive ? "Purchases restored and verified." : "No active BACity+ subscription was found.");
    } catch { if (sameAccount()) setPlayMessage("BACity could not restore purchases right now."); }
    finally { if (sameAccount()) setWorking(false); }
  };

  const manageOnPlay = async () => {
    if (!playConfig?.package_name || !playConfig.product_id) return;
    const url = `https://play.google.com/store/account/subscriptions?sku=${encodeURIComponent(playConfig.product_id)}&package=${encodeURIComponent(playConfig.package_name)}`;
    try { await Linking.openURL(url); }
    catch { setPlayMessage("Open Google Play subscriptions to manage BACity+."); }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <View style={styles.headerSpace} />
        <Text style={styles.brand}>BACity+</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Dismiss BACity Plus" onPress={dismiss} style={({ pressed }) => [styles.close, pressed && styles.pressed]}>
          <Ionicons name="close" size={22} color={colors.text} />
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.mark}><Ionicons name="sparkles" size={34} color={colors.white} /></View>
        <Text style={styles.title}>Premium discovery tools for deciding what to do.</Text>
        {feature ? <Text style={styles.context}>{PLUS_FEATURES[feature]} is planned as a BACity+ feature.</Text> : null}
        {params.unavailable === "1" ? <Text style={styles.notice}>We could not verify your access right now. Try again when your connection is available.</Text> : null}
        {returnMessage ? <Text style={styles.notice}>{returnMessage}</Text> : null}
        {billingError ? <Text style={styles.notice}>{billingError}</Text> : null}
        {playMessage ? <Text style={styles.notice}>{playMessage}</Text> : null}
        {Platform.OS === "android" && active ? <Text style={styles.coming}>Your server-verified BACity+ access is active.</Text> : null}
        {Platform.OS === "android" && playConfig?.subscription_status === "expired" && !active ? <Text style={styles.coming}>Your Google Play subscription has expired.</Text> : null}
        {Platform.OS === "android" && playConfig?.subscription_status === "pending" ? <Text style={styles.coming}>Google Play is still processing your purchase. Restore purchases after payment completes.</Text> : null}
        {Platform.OS === "android" && playProduct && !active ? <Text style={styles.coming}>Automatically renews until cancelled. Manage or cancel in Google Play.</Text> : null}
        <View style={styles.list}>
          {Object.values(PLUS_FEATURES).map(label => (
            <View key={label} style={styles.row}>
              <View style={styles.check}><Ionicons name="checkmark" size={15} color={colors.primaryDark} /></View>
              <Text style={styles.label}>{label}</Text>
            </View>
          ))}
        </View>
        {Platform.OS === "web" && billing?.cancel_at_period_end && billing.current_period_end ? (
          <Text style={styles.coming}>Active until {new Date(billing.current_period_end).toLocaleDateString()}; renewal is cancelled.</Text>
        ) : null}
        {canShowWebPurchase(Platform.OS, billing?.billing_enabled === true, billing?.checkout_available === true) ? (
          <Pressable disabled={working} accessibilityRole="button" onPress={() => void openProvider(createConsumerCheckout)} style={({ pressed }) => [styles.button, (pressed || working) && styles.pressed]}>
            <Text style={styles.buttonText}>{working ? "Verifying…" : "Subscribe on web"}</Text>
          </Pressable>
        ) : null}
        {Platform.OS === "web" && billing?.portal_available ? (
          <Pressable disabled={working} accessibilityRole="button" onPress={() => void openProvider(createConsumerPortal)} style={({ pressed }) => [styles.secondaryButton, (pressed || working) && styles.pressed]}>
            <Text style={styles.secondaryText}>Manage billing</Text>
          </Pressable>
        ) : null}
        {Platform.OS === "web" && returned === "success" && !active && !working ? (
          <Pressable accessibilityRole="button" onPress={() => void verifySubscription()} style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}>
            <Text style={styles.secondaryText}>Retry verification</Text>
          </Pressable>
        ) : null}
        {Platform.OS === "android" && playConfig?.cancel_at_period_end && playConfig.current_period_end ? (
          <Text style={styles.coming}>Active until {new Date(playConfig.current_period_end).toLocaleDateString()}; renewal is cancelled.</Text>
        ) : null}
        {canStartPlayPurchase(Platform.OS, playConfig?.configured === true, !!playProduct, active, playConfig?.active_paid_other_provider === true) ? (
          <Pressable disabled={working} accessibilityRole="button" onPress={() => void purchaseOnPlay()} style={({ pressed }) => [styles.button, (pressed || working) && styles.pressed]}>
            <Text style={styles.buttonText}>{working ? "Working…" : `Subscribe · ${playProduct?.localizedPrice ?? ""} / ${{ P1M: "month", P1Y: "year", P1W: "week", P3M: "3 months", P6M: "6 months" }[playProduct?.billingPeriod ?? ""] ?? playProduct?.billingPeriod}`}</Text>
          </Pressable>
        ) : null}
        {Platform.OS === "android" && playConfig?.active_paid_other_provider ? <Text style={styles.coming}>BACity+ is active through another provider. A second subscription is blocked to avoid duplicate billing.</Text> : null}
        {Platform.OS === "android" && playConfig?.configured ? (
          <Pressable disabled={working} accessibilityRole="button" onPress={() => void restoreOnPlay()} style={({ pressed }) => [styles.secondaryButton, (pressed || working) && styles.pressed]}>
            <Text style={styles.secondaryText}>Restore purchases</Text>
          </Pressable>
        ) : null}
        {Platform.OS === "android" && (playConfig?.management_channel === "play_store" || (playConfig?.subscription_status && !["expired", "replaced"].includes(playConfig.subscription_status))) ? (
          <Pressable disabled={working} accessibilityRole="button" onPress={() => void manageOnPlay()} style={({ pressed }) => [styles.secondaryButton, (pressed || working) && styles.pressed]}>
            <Text style={styles.secondaryText}>Manage in Google Play</Text>
          </Pressable>
        ) : null}
        {Platform.OS === "android" && playConfig?.configured === false ? <Text style={styles.coming}>Google Play purchasing is currently unavailable.</Text> : null}
        {Platform.OS === "android" && billingError ? (
          <Pressable disabled={working} accessibilityRole="button" onPress={() => {
            setBillingError(null);
            void loadPlay().catch(() => { if (sameAccount()) setBillingError("Google Play Billing is temporarily unavailable."); });
          }} style={styles.secondaryButton}><Text style={styles.secondaryText}>Retry Google Play</Text></Pressable>
        ) : null}
        {Platform.OS === "android" && !playConfig && !billingError ? <Text style={styles.coming}>Loading Google Play products…</Text> : null}
        {Platform.OS === "android" && playConfig?.configured && !playProduct ? <Text style={styles.coming}>No eligible subscription product is available on this device.</Text> : null}
        {Platform.OS === "ios" ? <Text style={styles.coming}>App Store purchasing is not available yet. Existing verified access still works.</Text> : null}
        {Platform.OS === "web" && billing?.billing_enabled === false ? <Text style={styles.coming}>Web purchasing is currently unavailable.</Text> : null}
        <Pressable accessibilityRole="button" onPress={dismiss} style={({ pressed }) => [styles.button, pressed && styles.pressed]}>
          <Text style={styles.buttonText}>Not now</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { minHeight: 58, paddingHorizontal: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  headerSpace: { width: 44 }, brand: { color: colors.text, fontFamily: fonts.black, fontSize: 18 },
  close: { width: 44, height: 44, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  content: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 30, paddingBottom: 32, alignItems: "center" },
  mark: { width: 72, height: 72, borderRadius: 25, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", marginBottom: 24 },
  title: { maxWidth: 330, color: colors.text, fontFamily: fonts.black, fontSize: 29, lineHeight: 33, letterSpacing: -1, textAlign: "center" },
  context: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 13, lineHeight: 19, textAlign: "center", marginTop: 14 },
  notice: { width: "100%", color: colors.danger, fontFamily: fonts.medium, fontSize: 12, lineHeight: 18, textAlign: "center", backgroundColor: "#FFF0F1", borderRadius: 14, padding: 12, marginTop: 14 },
  list: { width: "100%", marginTop: 30, gap: 12 },
  row: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: 12 },
  check: { width: 30, height: 30, borderRadius: 11, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  label: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
  coming: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, textAlign: "center", marginTop: 28 },
  button: { width: "100%", minHeight: 54, borderRadius: 18, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", marginTop: 18 },
  buttonText: { color: colors.white, fontFamily: fonts.black, fontSize: 14 }, pressed: { opacity: .75, transform: [{ scale: .98 }] },
  secondaryButton: { width: "100%", minHeight: 50, borderRadius: 18, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center", marginTop: 10 },
  secondaryText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
});
