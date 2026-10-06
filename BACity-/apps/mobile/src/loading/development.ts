import { developmentDelay } from './policy';
/** Explicit dev-only event-detail latency, no transport/production behavior change. */
export async function withLoadingTestDelay<T>(operation: () => Promise<T>) {
  const ms = developmentDelay(__DEV__, process.env.EXPO_PUBLIC_LOADING_TEST_DELAY_MS);
  if (ms) await new Promise(resolve => setTimeout(resolve, ms));
  return operation();
}
