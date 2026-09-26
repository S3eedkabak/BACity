# Profile media operations

Profile photos are selected through the native Expo image editor with a square crop. The API accepts JPEG, PNG, or WebP up to 5 MB, rejects images below 128×128 or above 30 megapixels, strips metadata, center-fits the result, and stores a 512×512 JPEG. Client filenames and file extensions are never used as storage paths.

Production stores avatars in the named `media` volume mounted at `/data/media`. Caddy serves them through the API's `/media` route. The daily backup service creates and validates a matching `bacity-media-*.tar.gz` beside each PostgreSQL dump and applies the same 14-day retention.

Restore the database dump and media archive from the same backup cycle. After restoration, verify that the `users.avatar_url` path resolves and that deleted-account avatars are absent. For multi-host deployment, replace the local volume with private object storage plus signed administrative access; keep public reads limited to rendered avatar derivatives.
