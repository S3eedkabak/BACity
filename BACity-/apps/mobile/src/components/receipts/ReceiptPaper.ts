import { StyleSheet } from 'react-native';
import { receiptInk, receiptMono } from './ReceiptPrinterView';

export const paper = StyleSheet.create({
  wordmark: { color: receiptInk, fontSize: 27, fontWeight: '800', letterSpacing: -1.2, textAlign: 'center' },
  title: { color: receiptInk, fontFamily: receiptMono, textAlign: 'center', fontWeight: '700', fontSize: 12, letterSpacing: 1, marginTop: 13, lineHeight: 18 },
  copy: { color: '#51474E', fontSize: 12, lineHeight: 19, fontFamily: receiptMono, marginTop: 7 },
  rule: { height: 1, borderTopWidth: 1, borderStyle: 'dashed', borderColor: '#B4A79E', marginVertical: 19 },
  day: { color: receiptInk, fontFamily: receiptMono, fontSize: 11, fontWeight: '700', lineHeight: 18, letterSpacing: .7, marginVertical: 8 },
  stop: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#D9CDC2', paddingVertical: 15 }, time: { color: '#8D2856', fontFamily: receiptMono, fontSize: 11, fontWeight: '600', lineHeight: 18 },
  touch: { minHeight: 44, justifyContent: 'center', paddingVertical: 5 }, event: { color: receiptInk, fontWeight: '700', fontSize: 16, lineHeight: 23, letterSpacing: -.3 },
  location: { minHeight: 44, justifyContent: 'center' }, reason: { color: '#6F5C65', fontSize: 11, lineHeight: 17, marginTop: 3 }, notice: { color: '#8D2856', fontSize: 11, lineHeight: 18, marginTop: 7 },
  footer: { color: receiptInk, fontFamily: receiptMono, fontSize: 11, textAlign: 'center', fontWeight: '700', lineHeight: 18 }, disclaimer: { color: '#6F5C65', fontSize: 10, lineHeight: 16, textAlign: 'center', marginTop: 12 },
  barcode: { flexDirection: 'row', gap: 3, justifyContent: 'center', alignItems: 'flex-start', marginTop: 24 }, signature: { color: '#6F5C65', fontFamily: receiptMono, fontSize: 8, letterSpacing: .6, textAlign: 'center', marginTop: 12, lineHeight: 15 },
});
