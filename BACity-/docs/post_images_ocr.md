# Private post images and free poster OCR

Post images now appear in **Events to review** and in each publisher's **Recent checks & collected posts**. Select **Text read from this image** to inspect the extracted text. Selecting an image opens the private cached preview. The original post link remains available for full-resolution source material.

## How it works

Caption ingestion remains independent. After an observation is saved, the isolated collector processes up to three existing image references per post. It downloads public Instagram/Meta CDN images through restricted egress, decodes only bounded JPEG/PNG/WebP raster images, removes metadata by re-encoding, caches a JPEG preview and runs Tesseract locally with **Slovak, Czech and English** language data. There is no paid OCR API, OCR subscription, new key or runtime model download. Existing Apify/ScrapingAnt collection still follows its existing provider billing and budget rules; image processing does not launch another provider crawl or reset the daily allowance.

OCR uses grayscale/contrast adjustment, coloured-letter preservation, inversion when needed, multiple text scales and sparse/block segmentation. Noise-only lines do not outrank coherent words. Original captions remain unchanged. Useful poster text feeds draft event extraction; poster paragraphs are treated as one coherent evidence block, obvious giveaway posters do not automatically produce event drafts, duplicate slide suggestions are skipped, and OCR suggestions **always require review**. Existing reviewed/published candidates are not rewritten. Check dates, names, prices and venue information against the image before approving: decorative fonts, curved/rotated lettering, photo backgrounds and small text can still be read imperfectly.

Tesseract is open-source software under Apache 2.0. References: [installation/language data](https://tesseract-ocr.github.io/tessdoc/Installation.html), [image-quality guidance](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html).

## Isolation and durability

- Panel browsers load authenticated, same-origin `/api/post-images/<id>` previews. They do not contact Instagram CDNs or receive those image URLs from the gallery endpoint. Consumer login/JWTs do not grant access.
- Source fetches allow only HTTPS Instagram/Meta CDN suffixes, no arbitrary hosts/ports, redirects, credentials, private addresses or DNS rebinding. Existing public-IP pinning and TLS checks remain. The restricted proxy permits those CDN suffixes while still resolving/pinning public addresses.
- Input images are limited to 4 MiB/12 million pixels. The image/OCR subprocess receives no provider tokens, worker key or database connection. Its process group is killed on timeout. Four OCR passes are each bounded to six seconds; the parent image job is bounded to 38 seconds. The collector remains non-root, read-only outside its existing mounts, without capabilities, with 512 MiB memory and restricted egress.
- Previews are bounded to 40,000 bytes; extracted text to 3,500 UTF-8 bytes. These are cached previews rather than original full-resolution files. At most 15,000 private image rows exist; capacity exhaustion pauses new image work rather than deleting pending evidence.
- Media results use the existing fsync-backed outbox and transactional delivery receipts. A database/gateway outage retains the completed preview/text for delivery; a restart reuses the saved result instead of redownloading it. The journal clears only after commit acknowledgement.
- Fetch failures/timeouts have at most three bounded attempts with backoff. An OCR failure retains the image and caption; it never fails an otherwise collected post. Expired CDN URLs can leave an image unavailable, in which case the original source link and saved caption remain.
- Already-collected post images can be processed while publisher monitoring is paused, provided source approval and collection access are still valid. Suspension, withdrawn approval, access restrictions and emergency stops remain enforced. No new source collection is enabled by processing an existing image.
- PostgreSQL table `l4_post_images` stores previews/text privately, linked to observations with deletion cascade. Images and OCR follow the same observation retention window, including the underlying bytes. Staff can read but cannot upload/overwrite image work; the machine gateway has narrowly scoped table grants. No public event/media tables or public API behavior change.

## Deployment and existing posts

Migration **0029** adds only the private image table. Back up PostgreSQL, apply the migration as the owner, reapply `infrastructure/social/roles.sql`, then rebuild/recreate `social-admin`, `social-gateway`, `social-collector`, `social-egress` and `social-retention`. Keep the same outbox volume. The collector image installs Tesseract and language data during the build; the server does not need a separate OCR installation.

Image references in existing retained observations are queued automatically. No new crawl is required for those posts. The normal daily source schedule and maximum two posts remain unchanged. Images usually appear shortly after their captions; the review gallery checks processing status automatically. Advanced operators can disable new image work with `SOCIAL_MEDIA_ENABLED=false` in the private social configuration and recreate the relevant services. This does not delete stored previews or captions.

## Validation

Tests cover real local Tesseract recognition, authenticated image serving and desktop/phone display, timeout fallbacks, non-image payload rejection, image limits and host restrictions, new OCR drafts without changing reviewed candidates, duplicate slides/receipt replay, capture persistence across gateway outages, real PostgreSQL restricted-role image writes and retention cascades, and the existing provider/passkey/outage regression suites. OCR fixtures do not call paid providers.
