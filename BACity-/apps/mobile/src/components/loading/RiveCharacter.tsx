import { useEffect, useState, useRef } from 'react';
import { StyleSheet, UIManager, View } from 'react-native';
import { walkAsset } from '../../loading/registry';
export function RiveCharacter({ animation, onFailure }: { animation: string; onFailure: () => void }) {
  const [runtime, setRuntime] = useState<typeof import('rive-react-native')>();
  const timeout = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    let alive = true;
    if (!UIManager.getViewManagerConfig('RiveReactNativeView')) { onFailure(); return; }
    try { setRuntime(require('rive-react-native')); } catch { onFailure(); return; }
    timeout.current = setTimeout(() => { if (alive) onFailure(); }, 4000);
    return () => { alive = false; clearTimeout(timeout.current); };
  }, [onFailure]);
  const Player = runtime?.default;
  // The supplied artboard includes demo level buttons along its bottom edge.
  // Crop only that control strip, without altering the binary or stretching it.
  return <View pointerEvents="none" style={styles.crop}>
    {Player && runtime && <Player resourceName="bacity_walk" artboardName={walkAsset.artboard} animationName={animation} autoplay fit={runtime.Fit.Contain} style={styles.artboard} onPlay={() => { clearTimeout(timeout.current); if (__DEV__) console.debug('[RiveCharacter] initialized', animation); }} onError={onFailure} />}
  </View>;
}
const styles = StyleSheet.create({ crop: { width: 280, height: 280, overflow: 'hidden', borderRadius: 28 }, artboard: { width: 280, height: 350 } });
