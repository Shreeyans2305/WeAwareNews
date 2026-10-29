# WeAware for iOS

Native SwiftUI application for iOS 17 and later. Open `WeAware.xcodeproj` in Xcode, select an iPhone simulator and Run. There are no external package dependencies. The default API points at the existing deployed WeAware service.

## Configuration

The app is registered as `news.weaware.ios` in Firebase project `weaware-3504c`. Copy `Config.local.xcconfig.example` to `Config.local.xcconfig` and supply the current iOS Firebase API key, iOS OAuth client ID, and reversed callback scheme. The local file is ignored by Git and optionally included by the shared `Config.xcconfig`. No Firebase plist is required. Without local settings, public reading works and account features request configuration.

Restrict the iOS key to bundle ID `news.weaware.ios` and APIs `identitytoolkit.googleapis.com` and `securetoken.googleapis.com`. Both authentication and refresh requests send `X-Ios-Bundle-Identifier`. Keep the `https:/$()/` syntax for `API_ORIGIN` because `//` starts an xcconfig comment. Never add administrator credentials or OAuth client secrets.

Enable email/password and Google providers in the existing Firebase project. Email verification and password resets use Firebase's configured action URLs. Google sign-in uses the system authentication browser with PKCE, validates OAuth state, then exchanges the Google identity for a Firebase session. Refresh tokens are stored in Keychain with this-device-only protection. Tokens are refreshed before protected requests; verification reload explicitly refreshes the token.

For physical device builds select your Apple development team in Signing & Capabilities. No certificates or credentials are included. App Store distribution still needs the app icon, privacy declarations, signing, screenshots and review. Story links use `https://weaware-3504c.web.app/s/{id}`. The app handles incoming links for that host; deploy `WEAWARE/public/.well-known/apple-app-site-association` with the website so iOS can verify the Universal Link association.

## Implemented

- Published news, topic filters, debounced search, pagination, pull to refresh, guest preview/read limit.
- Native reader, source agreement, original source links, claim warnings, local likes, story sharing.
- Article narration request/polling, five-story queue, podcast playback, previous/next in episode and article queues, seek/skip/speed, background audio and system playback controls.
- Published podcast sources, RSS sharing, server-authorized draft review and approval.
- Email/password and Google sign-in, registration, verification, reset, durable sessions and sign-out.
- Newsletter topics, explicit consent, daily/weekly delivery, test email and unsubscribe.
- Sherlock entitlement, idempotent submission, all report lengths, notebook, cancellation, polling, approved briefs, per-paragraph evidence, discovery source links and authenticated PDF sharing.
- System/light/dark appearance, Dynamic Type and native accessibility controls.

## Validation

```sh
xcodebuild -project mobile/ios/WeAware.xcodeproj -scheme WeAware \
  -sdk iphonesimulator -configuration Debug \
  -derivedDataPath /tmp/weaware-ios-build CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=- build
```

A simulator SDK build was validated with Xcode 27.1, then installed and launched on an iPhone 17 Pro simulator (iOS 26.2). The live feed loaded articles, images and topics. Public deployed article/topic/podcast payloads were decoded against the Swift models. Firebase identifiers and the Google callback scheme are configured; account-specific operations still need a signed-in test account; Google callback, email delivery, private research access, playback on physical devices and editor approval require end-to-end verification before release. No emails were sent and no research credits or approval actions were consumed during implementation.

## Google sign-in in Simulator

On this Mac, iOS 26.2 repeatedly crashes Apple WebKit during Google sign-in, including inside Safari. Use the installed iPhone 17 Pro running iOS 26.5 for account testing. Restarting 26.2 alone did not resolve it; do not erase user data or loosen Firebase key restrictions as a workaround. The app allows cancelling a pending Google login and times out after three minutes if the system browser never completes. Browser callbacks are matched to their attempt so late callbacks cannot complete a new sign-in.

The iOS 26.5 Google page, cancellation and reopening were smoke tested. After the signing fix below, the user completed live Google sign-in; the verified account remained signed in after terminating and relaunching the app.

## Authentication regression tests

Simulator builds must keep signing enabled. Disabling it omitted the simulator application identifier entitlement and caused Keychain error `-34018` after otherwise successful Google authentication. The Account model now publishes a signed-in profile only after profile validation and secure persistence succeed. Existing session data is updated without deleting it first, startup restoration errors are visible, and temporary refresh failures preserve the current account.

```sh
xcodebuild -project mobile/ios/WeAware.xcodeproj -scheme WeAware \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=26.5' \
  -derivedDataPath /tmp/weaware-ios-signed \
  CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=- test
```

These hosted tests exercise real simulator Keychain save/update/read/delete and use intercepted network responses for session transitions, persistence failure, restoration, and refresh errors. They do not create production accounts or send email.
