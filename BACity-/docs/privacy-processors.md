# Processor / provider inventory

Verified code/config capability is not proof a vendor is enabled in production, is a processor rather than independent controller, has an EEA region, or has signed terms. Owner must confirm role/service account/region/subprocessors/DPA/security/deletion/transfer terms before launch.

| Service | Purpose / data leaving BACity | Role / destination | Deletion capability / required action |
|---|---|---|---|
| Hosting/Postgres/backup/media operator | All persisted categories/IP access logs/backups | Provider not identified; role/region UNCONFIRMED | Configure access/encryption/retention/restore reconciliation; obtain DPA if applicable |
| Configured SMTP/Brevo | Transactional recipient/from/action link/service body | SMTP configured externally; role/region/subprocessors UNCONFIRMED | Local outbox cleanup != provider erasure; verify relay retention, DPA and support/API procedure |
| Google OAuth | Sign-in identifiers/verified email, callback | Google role/region/terms review | Local links removed; user/provider connected-account controls; do not revoke arbitrary Google records |
| Apple Sign in | Identity/email relay/revocation credential | Enabled OAuth capability; Apple IAP absent | Existing token revocation attempt; manual user revocation if provider fails; contract review |
| Google Play | Subscriber purchase/package/product/opaque account binding, RTDN | Provider may independently process payments; region/role review | Store-managed cancellation; no blind financial record deletion; Data Safety/retention review |
| Stripe consumer | Customer/account metadata, subscription and checkout state | Hosted Checkout/Portal; BACity does not collect card details | Existing safe cancellation; customer/invoice deletion obligations need review |
| Stripe organization | Organization/customer/subscription business metadata | Separate B2B contract/role | Preserve organization ownership and financial record obligations; no blanket consumer deletion |
| OpenFreeMap style/vector-tile hosts | Client IP and requested map tile area | Native MapLibre configured OpenFreeMap; terms/operator review | Cache/request retention unknown; document host/attribution and deployment contact |
| Public event source hosts | Crawler IP/user agent/public page URL | Not automatically processors; publisher relationships review | Public event extraction only, robots/rate restrictions; no private scraping |
| User-selected share destination | Export chosen by requester | User's chosen destination, not automatic BACity processor | Warn export is private; destination responsibility reviewed by user |

NONE FOUND: installed third-party analytics/crash/ads/attribution/push processing integration. First-party organizer aggregate analytics and sponsored promotions do exist.

For each contracted processor obtain: processing instructions/purpose/data/subjects; confidentiality; security measures; subprocessor authorization/list; incident notification; rights assistance; deletion/return; audit assurance; transfer mechanism. No agreements are fabricated. Vendor erasure may require operational action; never delete provider accounting/fraud records blindly. Actual vendor regions and legal roles remain launch blockers.
