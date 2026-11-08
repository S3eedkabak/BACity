import { Text } from "react-native";
import { Page, Disclosure, ui } from "../src/components/CommunityUI";
import { interactionNotices } from "../src/legal/thirdPartyNotices";
export default function LicensesScreen() {
  return (
    <Page title="Open source licenses">
      <Text style={ui.text}>
        BACity includes the following interaction libraries and native
        adaptations. Their license texts are reproduced below.
      </Text>
      {interactionNotices.map((notice) => (
        <Disclosure
          key={notice.name}
          title={`${notice.name} · ${notice.license}`}
          icon="document-text-outline"
        >
          <Text selectable style={ui.muted}>
            {notice.url}
          </Text>
          <Text selectable style={ui.text}>
            {notice.text}
          </Text>
        </Disclosure>
      ))}
    </Page>
  );
}
