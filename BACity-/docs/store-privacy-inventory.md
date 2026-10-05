# Store privacy disclosure input — not submitted

[Google Data Safety](https://support.google.com/googleplay/android-developer/answer/10144311?hl=en), [Google account deletion](https://support.google.com/googleplay/android-developer/answer/13327111?hl=en), [Apple App Privacy](https://developer.apple.com/help/app-store-connect/reference/app-privacy/), [Apple account deletion](https://developer.apple.com/support/offering-account-deletion-in-your-app). Owner must verify exact release build, SDK versions, vendor processing and console definitions before submission.

| Data | Processing evidence | Disclosure question requiring store review |
|---|---|---|
| Email/name/account ID | Authentication/profile/provider mapping | Linked identity/contact data, purpose and retention |
| Profile/photo/content | Avatar/gallery, bio/contributions/reviews | User content and public/private treatment |
| Messages | Pair messages AEAD at rest; server decrypts | Private communication/content collection, not E2EE |
| Follows/saves/interests | Personalized discovery/social graph | Product interaction/other user content and linked use |
| Coarse location | Foreground optional request; no intentional history | Ephemeral processing vs collection definitions; tile/provider logs |
| Area Watch location | Owner-private persisted center | Must not classify all location ephemeral |
| Groups/preferences/votes | Private matching/voting data | Content/interaction linked account |
| Purchase/subscription state | Provider identifiers/status/tokens; no card entry in BACity | Purchase history, service/processor sharing definitions |
| Privacy requests | Encrypted case text/status | User support content, linked identity before erasure |
| Diagnostics/IPs | App safe statuses; proxy/vendor logs unverified | Release/vendor actual collection, not blanket none |

Native permissions: foreground approximate/precise Android location permissions remain for existing Expo capabilities; coordinates coarsened after acquisition. Gallery/library only for avatars. New Android merge removals block camera/microphone/background location/activity recognition; Info.plist now supplies actual when-in-use and photo purpose strings. No contacts permission/request found. Biometric declarations come from secure storage; no explicit new biometric collection. Legacy external-storage permission, debug overlay and network/WiFi permissions need release-SDK/device verification before declarations. Checked-in iOS native build cannot be validated on Windows.

No push/ads/tracking SDK found. First-party organizer analytics and labeled promotions exist. Do not tick no data collected merely because transport/storage encrypted. Required external deletion URL and published privacy policy must be configured; current pre-production placeholders do not satisfy store submission.
