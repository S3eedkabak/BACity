# Collected posts and event drafts

A collected post is evidence, not an event. **Publishers → Recent checks & collected posts** keeps the original caption and cached poster images even when no event is found. **Events to review** shows actionable drafts; **Show past decisions** includes rejected, duplicate and published history.

Caption paragraphs stay together so a title, date, time and venue in different paragraphs support one event. Separate drafts require independently dated event headings. Repeated blocks are deduplicated. Entry instructions, ordinary promotions and giveaways without a separate explicit event schedule do not create drafts. Draw announcements and competition deadline lines cannot supply a party's schedule. For example, `Žrebujeme 29.10. o 19tej` means a giveaway draw on 29 October at 19:00; it does not establish the Halloween party schedule. Explicit event times such as `o 19tej` are supported when attached to actual event evidence.

Repeated announcements from the same publisher with the same normalized title, schedule and venue do not create another review entry. Each source post or edited version remains saved. Changed schedules and distinct events remain separate. Unknown dates do not automatically merge different posts. Matching is conservative: differently titled or cross-publisher announcements can still require human comparison. Existing canonical publication deduplication remains in place.

Caption and poster extraction share event filters. OCR suggestions require review. Giveaway captions cannot become events merely because decorative poster text resembles an event. Dates are not inferred from “Halloween week”, hashtags or draw deadlines. Genuine announcements containing a giveaway remain eligible when an explicit event schedule is separate from the promotion deadline.

## Upgrade cleanup

After backing up PostgreSQL, run the owner-only repair command from the app directory. It makes no provider requests or public event writes:

```sh
./control owner-run python -m app.social.reconcile_candidates
./control owner-run python -m app.social.reconcile_candidates --apply
```

The first command is a dry run. The second archives untouched legacy paragraph drafts as rejected, adds consolidated genuine drafts where appropriate and records the changes in the activity log. Captions, images and archived draft fields stay intact. Observations containing reviewed, staff-edited or publication-linked work are protected. Repeating the command is safe. The default batch is 100 observations; `--limit` accepts 1–1000.

Deploy updated social-admin, social-gateway and social-retention images before cleanup. Keep the existing outbox volume. This filtering update needs no new environment variable, provider crawl or schema migration. Historical crawl metrics are not rewritten when legacy drafts are archived.
