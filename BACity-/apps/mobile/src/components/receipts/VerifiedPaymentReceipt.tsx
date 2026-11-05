import { useThemeRevision } from '../../theme/appearance';
import { ReactNode } from 'react';
import { Text, View } from 'react-native';
import { verifiedPayment, receiptDate } from '../../receipts/presentation';
import { ReceiptPrinterView } from './ReceiptPrinterView';
import { paper } from './ReceiptPaper';
import { colors } from '../../theme/colors';

export type PaymentReceiptState =
  | { status: 'pending' | 'cancelled' | 'failed' | 'unavailable' }
  | { status: 'verified'; backendReceipt: unknown };

/** Integration seam only. Callers must supply an authenticated backend receipt,
 * never purchase callbacks, entitlements, tokens or Checkout return parameters.
 * Current BACity billing does not yet expose this transaction data contract. */
export function VerifiedPaymentReceipt({ state, officialDocumentAction }: { state: PaymentReceiptState; officialDocumentAction?: ReactNode }) {
  useThemeRevision();
  const payment = state.status === 'verified' ? verifiedPayment(state.backendReceipt) : null;
  if (state.status !== 'pending' && !payment) return <View style={{ paddingVertical: 16, gap: 12 }}>
    <Text accessibilityLiveRegion="polite" style={{ color: colors.textMuted, lineHeight: 22 }}>{
      state.status === 'cancelled' ? 'Payment cancelled. No paid receipt is available.' : state.status === 'failed' ? 'Payment was not confirmed. No paid receipt is available.' : 'A verified transaction receipt is not available. Your provider remains the source for billing documents.'
    }</Text>{officialDocumentAction}
  </View>;
  return <ReceiptPrinterView title="Payment confirmation" pending={!payment} resultKey={payment?.receipt_id ?? null}
    summary={payment?.product ?? ''} processingLabel="Waiting for backend payment confirmation" completeLabel="Payment confirmed">
    {payment && <>
      <Text style={paper.wordmark}>BACity+</Text><Text style={paper.title}>PAYMENT CONFIRMATION</Text><View style={paper.rule} />
      <Text style={paper.event}>{payment.product}</Text><Text style={paper.copy}>{receiptDate(payment.paid_at)} · {new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Bratislava', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(payment.paid_at))} (Bratislava)</Text>
      <Text style={paper.copy}>Total paid: {payment.currency} {(payment.amount_minor / 10 ** payment.currency_exponent).toFixed(payment.currency_exponent)}</Text>
      <Text style={paper.copy}>Reference: {payment.transaction_reference}</Text>
      {payment.merchant_name && <Text style={paper.copy}>{payment.merchant_name}</Text>}
      <View style={paper.rule} /><Text style={paper.footer}>PAID · BACKEND CONFIRMED</Text>
      <Text style={paper.disclaimer}>Transaction confirmation. This does not replace the provider's official invoice or tax document.</Text>
      {officialDocumentAction}
    </>}
  </ReceiptPrinterView>;
}
