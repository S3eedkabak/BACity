# International-transfer checklist

No production deployment region or provider contract is available in repository evidence. Do not infer EEA residency from BACity's Bratislava purpose or a provider brand.

| Flow | Region/mechanism established? | Required verification | Owner/status |
|---|---|---|---|
| Hosting/backup/media | No | Hosting regions, support access, subprocessors, storage/backup keys | Operations; PRODUCTION CONFIG REQUIRED / contractual review |
| SMTP relay | No | Relay/log/archive/support location and contractual scope | Owner; PROCESSOR/CONTRACT REQUIRED |
| OAuth Google/Apple | No | Roles, regional processing, onward access and legal terms | Counsel; PROCESSOR/CONTRACT REQUIRED |
| Stripe consumer/org | No | Independent-controller vs processor activities, terms/regions | Counsel; PROCESSOR/CONTRACT REQUIRED |
| Google Play/RTDN | No | Store/payment role, support regions and contractual safeguards | Counsel; PROCESSOR/CONTRACT REQUIRED |
| Tile hosts/client maps | No | Actual host/operator/request logs and applicable terms | Operations/Counsel; review required |

Counsel must identify each actual destination and, where required, validate adequacy, contractual safeguards/SCCs, transfer assessment and supplementary measures. Do not assert SCC/adequacy coverage just because a provider advertises it. Server encryption helps snapshot exposure; providers receiving plaintext identity/email/payment requests can still access that data. Local telemetry/proxy additions require re-inventory. Until actual transfers are assessed, launch blocker TRANSFER-001 remains.
