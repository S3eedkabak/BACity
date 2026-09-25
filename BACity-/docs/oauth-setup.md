# BACity social sign-in setup

The mobile app uses the BACity API as the OAuth broker and returns to the app through the existing `bratislava-events://oauth` deep link. Provider secrets remain server-side.

## Google

Create a Google OAuth web client and register:

```text
<OAUTH_CALLBACK_BASE_URL>/auth/oauth/google/callback
```

Set:

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

For local Android development, `OAUTH_CALLBACK_BASE_URL=http://localhost:8000` works only when the browser/provider can reach that URL. A staging HTTPS API is the more reliable device test path.

## Apple

Create a Sign in with Apple Service ID, associate it with the app/site, create a Sign in with Apple private key, and register:

```text
<OAUTH_CALLBACK_BASE_URL>/auth/oauth/apple/callback
```

Set:

```env
APPLE_OAUTH_CLIENT_ID=
APPLE_TEAM_ID=
APPLE_KEY_ID=
APPLE_PRIVATE_KEY=
```

`APPLE_OAUTH_CLIENT_ID` is the Service ID used for the web authorization flow. Store the PEM key on one env-file line with newlines escaped as `\n`.

Apple web sign-in requires an HTTPS return URL on a verified domain. Use staging or a trusted HTTPS tunnel for Android/local testing.

## Mobile return route

Keep:

```env
OAUTH_APP_REDIRECT_URI=bratislava-events://oauth
```

The flow is:

```text
BACity app -> BACity API -> Google/Apple -> BACity API callback
-> bratislava-events://oauth?code=... -> BACity API exchange -> BACity JWT
```

Provider buttons remain visible when credentials are absent, but the app explains that the provider still needs server configuration rather than pretending authentication succeeded.
