# BACity social sign-in setup

BACity supports native Google and Apple sign-in in installed builds. The existing browser flow remains available and returns through `bratislava-events://oauth`. Provider secrets and the Apple signing key remain server-side.

## Google

Create three OAuth clients in one Google Cloud project:

- Web: server-side verification and the existing browser flow.
- Android: package `com.bratislavaevents.app` plus the production signing certificate SHA-1.
- iOS: bundle ID `com.bratislavaevents.app`; copy its iOS client ID and reversed URL scheme.

Register this redirect URI on the web client:

```text
<OAUTH_CALLBACK_BASE_URL>/auth/oauth/google/callback
```

Set:

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_ANDROID_CLIENT_ID=
GOOGLE_IOS_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME=
```

For local Android development, `OAUTH_CALLBACK_BASE_URL=http://localhost:8000` works only when the browser/provider can reach that URL. A staging HTTPS API is the more reliable device test path.

## Apple

Enable **Sign in with Apple** for App ID `com.bratislavaevents.app`. Create and associate a Service ID for the browser flow, create a Sign in with Apple private key, and register:

```text
<OAUTH_CALLBACK_BASE_URL>/auth/oauth/apple/callback
```

Set:

```env
APPLE_OAUTH_CLIENT_ID=
APPLE_IOS_CLIENT_ID=com.bratislavaevents.app
APPLE_TEAM_ID=
APPLE_KEY_ID=
APPLE_PRIVATE_KEY=
OAUTH_TOKEN_ENCRYPTION_KEY=
```

`APPLE_OAUTH_CLIENT_ID` is the Service ID used for the web flow; `APPLE_IOS_CLIENT_ID` is the native App ID. Store the PEM key on one env-file line with newlines escaped as `\n`. Generate the independent encryption key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, store it in the secret manager, and back it up separately from the database.

Apple web sign-in requires an HTTPS return URL on a verified domain. Use staging or a trusted HTTPS tunnel for Android/local testing.

## Mobile return route

Keep:

```env
OAUTH_APP_REDIRECT_URI=bratislava-events://oauth
```

The browser flow is:

```text
BACity app -> BACity API -> Google/Apple -> BACity API callback
-> bratislava-events://oauth?code=... -> BACity API exchange -> BACity JWT
```

Native sign-in posts provider-signed identity material to `/auth/oauth/native`; the API verifies issuer, audience, signature/code, replay, and account-link conflicts before issuing a BACity JWT. Linking while signed in never moves an identity already attached to another account. Native sign-in requires a development/production build, not Expo Go.

For production validation and the Android/iOS test matrix, follow [production-auth-runbook.md](production-auth-runbook.md). Production configuration validation requires both providers.
