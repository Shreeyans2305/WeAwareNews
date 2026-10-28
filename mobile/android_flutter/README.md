# WeAware for Android

A Flutter Android app connected to the same FastAPI service and Firebase users as the website. It uses native Flutter screens rather than embedding the website.

## Run

Use Flutter 3.41 or later, Android Studio, and an Android SDK. From this directory:

```sh
flutter pub get
flutter run
```

Public reading and podcasts work without Firebase settings. The default API is the website's production service. Override it for development with `--dart-define=API_BASE_URL=https://your-api.example`. HTTP development servers require an explicit Android debug network security configuration; production connections use HTTPS.

## Connected accounts

This app is registered in the website's Firebase project `weaware-3504c` as `news.weaware.weaware`. Download `google-services.json` from Firebase into `android/app/`; this live configuration is ignored by Git. `google-services.example.json` documents its structure. The Google Services plugin applies only when the local file exists, so public reading still builds without account configuration. With the local file, Firebase and Google sign-in are configured automatically.

The current Mac's Android debug SHA-1 and SHA-256 certificates are registered. A different development machine or production signing key requires registering that key's certificate fingerprints in Firebase and downloading the updated configuration. Email/password and Google providers are enabled. Never include a service-account key, OAuth client secret, or server credential in this app.

Optional `FIREBASE_*` and `GOOGLE_WEB_CLIENT_ID` build flags remain available for a separate development project. Private services retain the backend's verified-email, invitation and editorial permission checks.

## Implemented

- Topic chips, explicit search submission, pull to refresh, pagination, and website-equivalent three readable guest stories with nine preview cards.
- Full mobile reader with source stance/notes/original links, agreement signal, flagged claims, publication metadata, original artwork, native sharing and disclosures.
- Shared foreground audio player across tabs, article narration request/polling, playback, seek, speed, queue and previous/next controls. Leaving an article does not dispose the player; controls remain on the main screen.
- Published podcast catalog, playback, RSS copy and session-local likes. Transcript and source fields render when included by the API.
- Firebase email/password sign-in, registration, Google sign-in, password reset, verification send/refresh and sign-out.
- Crosscheck saved topics, cadence, explicit consent, delivery status, test email and unsubscribe.
- Sherlock entitlement and credits, length/scope/question input, idempotent network retry, active history polling, queued cancellation, report reading with linked claim evidence and source notebook, authenticated PDF download/native share.
- Authorized podcast script/source review and explicit approval confirmation.
- System/light/dark appearance selector and About/editorial AI disclosures.

## Validation

```sh
flutter analyze
flutter test
flutter build apk --debug
```

Tests cover feed query encoding, structured research denials, preventing unauthenticated private calls, guest navigation and light/dark selection. Firebase is configured. Use your existing website account to exercise sign-in, account-scoped data, email delivery and invited research on a device. Do not generate billable research or editorial publication merely to smoke-test a build.

## Remaining release work

Register the production signing certificates and supply a final application identifier if different, final branding assets, release signing and Play Store metadata. The generated release Gradle configuration currently uses a **debug signing key** and must be changed before distribution. Foreground playback is implemented; Android background media service/notification/lock-screen playback is not yet enabled. App links for incoming shared stories require domain association and a routing implementation. This initial app does not add offline article caching or push notifications, which are not website features. No store upload or backend deployment is part of this scaffold.
