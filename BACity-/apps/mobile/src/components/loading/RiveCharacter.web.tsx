import { useEffect, useRef } from 'react';
import { Asset } from 'expo-asset';
import { Rive, RuntimeLoader, Fit, Layout } from '@rive-app/canvas';
import { walkAsset } from '../../loading/registry';
export function RiveCharacter({ animation, onFailure }: { animation: string; onFailure: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current) return;
    // Bundle WASM locally: no CDN dependency, tracking or third-party requests.
    RuntimeLoader.setWasmUrl(Asset.fromModule(require('@rive-app/canvas/rive.wasm')).uri);
    RuntimeLoader.setWasmFallbackUrl(null);
    const player = new Rive({ canvas: canvas.current, src: Asset.fromModule(require('../../../assets/rive/walk-cycle.riv')).uri,
      artboard: walkAsset.artboard, animations: animation, autoplay: true, layout: new Layout({ fit: Fit.Contain }),
      onLoad: () => clearTimeout(timeout), onLoadError: onFailure });
    const timeout = setTimeout(onFailure, 4000);
    return () => { clearTimeout(timeout); player.cleanup(); };
  }, [animation, onFailure]);
  return <div aria-hidden="true" style={{ width: 280, height: 280, overflow: 'hidden', borderRadius: 28, pointerEvents: 'none' }}><canvas ref={canvas} width={560} height={700} style={{ width: 280, height: 350 }} /></div>;
}
