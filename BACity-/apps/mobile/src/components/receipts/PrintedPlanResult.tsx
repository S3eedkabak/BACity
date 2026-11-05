import { useThemeRevision } from '../../theme/appearance';
import { ReactNode } from 'react';
import { Alert, Share, Text, View } from 'react-native';
import { router } from 'expo-router';
import { AnimatedPressable as Pressable } from '../motion/Motion';
import { ReceiptPrinterView, receiptInk } from './ReceiptPrinterView';
import { receiptTime, receiptVenue, sharePlan, stopNotice, type PrintedPlan } from '../../receipts/presentation';
import { eventCoordinates } from '../../map/eventLocation';
import { useViewOnMap } from '../../map/eventTarget';
import { paper } from './ReceiptPaper';

/** Receives the existing generated plan. No API, mutation, persistence or ranking. */
export function PrintedPlanResult({ plan, pending, resultKey, title, fallback, notice }: {
  plan: PrintedPlan | null; pending: boolean; resultKey: string | null; title: string; fallback?: ReactNode; notice?: string | null;
}) {
  useThemeRevision();
  const viewOnMap = useViewOnMap();
  async function share() {
    if (!plan) return;
    try { await Share.share({ title: plan.title, message: sharePlan(plan) }); }
    catch { Alert.alert('Could not share', 'Your result is still here. Please try again.'); }
  }
  if (!pending && (!plan || !plan.count)) return <>{fallback}</>;
  return <ReceiptPrinterView title={title} pending={pending} resultKey={plan?.count ? resultKey : null}
    summary={plan ? `${plan.count} ${plan.count === 1 ? 'stop' : 'stops'} · Europe/Bratislava` : ''}
    processingLabel={title === 'Build My Evening' ? 'Finding your evening' : 'Finding your weekend'} completeLabel="Your result is ready"
    fallback={fallback} onShare={share}>
    {plan && <>
      <Text style={paper.wordmark}>BACity+</Text><Text style={paper.title}>{plan.title.toUpperCase()}</Text>
      <Text style={paper.copy}>{plan.explanation}</Text>{notice && <Text style={paper.notice}>{notice}</Text>}<View style={paper.rule} />
      {plan.days.map(day => <View key={day.key}>
        <Text style={paper.day}>{day.label.toUpperCase()}</Text>
        {!day.stops.length && <Text style={paper.copy}>No events safely fit this day.</Text>}
        {day.stops.map(({ key, event, reason }) => <View key={key} style={paper.stop}>
          <Text style={paper.time}>{receiptTime(event)}</Text>
          <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.title}`} onPress={() => router.push(`/event/${event.id}`)} style={paper.touch}>
            <Text style={paper.event}>{event.title}</Text>
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel={eventCoordinates(event) ? `View ${event.title} on map` : `View details for ${event.title}`} style={paper.location}
            onPress={() => eventCoordinates(event) ? viewOnMap(event) : router.push(`/event/${event.id}`)}>
            <Text style={paper.copy}>{receiptVenue(event)} {eventCoordinates(event) ? '↗' : '→'}</Text>
          </Pressable>
          {reason && <Text style={paper.reason}>{reason}</Text>}
          {!!stopNotice(event) && <Text style={paper.notice}>{stopNotice(event)}</Text>}
        </View>)}
      </View>)}
      <View style={paper.rule} /><Text style={paper.footer}>{plan.count} STOPS · YOUR CITY</Text>
      <Text style={paper.disclaimer}>A suggested plan. Admission and reservations are not included.</Text>
      <View style={paper.barcode} accessibilityElementsHidden>{Array.from({ length: 35 }, (_, i) => <View key={i} style={{ height: 20 + i % 3 * 3, width: i % 4 === 0 ? 3 : 1, backgroundColor: receiptInk }} />)}</View>
      <Text style={paper.signature}>EXPLORE THE CITY. LIVE THE EXPERIENCE.</Text>
    </>}
  </ReceiptPrinterView>;
}

