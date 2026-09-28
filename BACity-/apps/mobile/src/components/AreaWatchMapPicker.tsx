import { Platform, StyleSheet, Text, View } from "react-native";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";

const nativeMapLibre = Platform.OS === "web" ? null : require("@maplibre/maplibre-react-native") as typeof import("@maplibre/maplibre-react-native");
const { Camera, CircleLayer, MapView, ShapeSource } = nativeMapLibre ?? ({} as typeof import("@maplibre/maplibre-react-native"));
const STYLE = "https://tiles.openfreemap.org/styles/liberty";

export function AreaWatchMapPicker({ latitude, longitude, radiusKm: _radiusKm, onChange }: { latitude: number; longitude: number; radiusKm: number; onChange: (latitude: number, longitude: number) => void }) {
  if (Platform.OS === "web" || !MapView) return <View style={styles.fallback}><Text style={styles.fallbackText}>Map selection is available in the Android and iOS app. Coordinates can still be entered below.</Text></View>;
  const point: GeoJSON.FeatureCollection<GeoJSON.Point> = { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [longitude, latitude] } }] };
  return <View style={styles.mapWrap}><MapView style={styles.map} mapStyle={STYLE} attributionEnabled logoEnabled={false} onPress={(event: GeoJSON.Feature) => { if (event.geometry.type !== "Point") return; const coordinates = event.geometry.coordinates; if (coordinates.length === 2) onChange(coordinates[1], coordinates[0]); }}><Camera centerCoordinate={[longitude, latitude]} zoomLevel={12} /><ShapeSource id="watch-center" shape={point}><CircleLayer id="watch-point" style={{ circleRadius: 7, circleColor: colors.primary, circleStrokeColor: colors.white, circleStrokeWidth: 2 }} /></ShapeSource></MapView><Text style={styles.hint}>Tap the map to choose the watch centre. Choose the exact radius below.</Text></View>;
}

const styles = StyleSheet.create({ mapWrap: { height: 220, borderRadius: 18, overflow: "hidden", backgroundColor: colors.surfaceAlt }, map: { flex: 1 }, hint: { position: "absolute", left: 10, right: 10, bottom: 8, textAlign: "center", color: colors.text, backgroundColor: "rgba(255,255,255,.9)", borderRadius: 10, padding: 6, fontFamily: fonts.medium, fontSize: 9 }, fallback: { minHeight: 90, borderRadius: 16, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center", padding: 16 }, fallbackText: { color: colors.textMuted, textAlign: "center", fontFamily: fonts.regular, fontSize: 10, lineHeight: 15 } });
