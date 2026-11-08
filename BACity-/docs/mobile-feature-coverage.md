# Mobile feature coverage

Backend route audit; backend implementation unchanged.

| Feature | Mobile entry point |
| --- | --- |
| Login, registration, OAuth, reset, verification | Welcome / Profile → Account |
| Profile and privacy, deletion | Profile → Account |
| Event discovery, search, map, saving | Discover / Map / Saved |
| Recommendations and sponsored events | Community → For you / Sponsored events |
| Venue details, events, follows | Event → More at venue |
| Places and utilities, status confirmations | Community → Places / City utilities |
| People, member profiles, follows, blocks | Community → People → Member |
| Reviews, helpful votes, comments, reports | Event / Place → Discussion |
| Messaging | Profile → Messages → received message, or People → Member |
| Notifications and read status | Profile → Notifications |
| Event/place/utility submissions | Create tab |
| Contribution decisions and appeals | Profile → Your contributions |
| Corrections | Event / Place discussion or Community utility card |
| Collection browsing and creation | Saved / Profile → Collections; detail → Create collection |
| Category and neighborhood follows | Community → Following |
| Organization registration and claims | Organizer → Find or register an organization |
| Organization editing, recurring events, analytics, billing | Profile → Organizer dashboard |
| Moderation submissions/reports/audit | Community, moderator/admin accounts |
| Role assignment | Member profile, admin accounts |

Removed the duplicate Create route wrapper; the contribution form is now the canonical Create-tab screen. Existing /contribute links resolve to it. Hidden Explore remains a working search screen linked from Discover.

Limits inherited from backend: Messages lists received-message notifications (latest 100), not a complete conversation inbox; outgoing conversations are accessed through members. Collection pickers use the first page of events, places and each utility kind, with the originating detail item always included. Billing requires server configuration. Ingestion, maintenance, webhooks and OAuth callbacks are service integration endpoints, not mobile screens.

Validation: TypeScript passes. Live authenticated/device flows were not exercised.
