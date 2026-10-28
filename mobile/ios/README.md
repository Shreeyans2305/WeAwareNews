# WeAware for iOS

Native SwiftUI application for iOS 17 and later. Open `WeAware.xcodeproj` in Xcode, select an iPhone simulator and Run. There are no external package dependencies. The default API points at the existing deployed WeAware service.

## Configuration

The app is registered as `news.weaware.ios` in the website’s Firebase project `weaware-3504c`. `Config.xcconfig` contains the public settings from the official Firebase client configuration. The app reads these build settings directly, so no additional Firebase plist is needed. Email/password and Google providers are enabled. No Firebase configuration is needed to run this simulator build.

For another Firebase project, update these public application settings in `Config.xcconfig`:

- `FIREBASE_API_KEY`: Firebase project's web API key. This is an application identifier, not a service-account credential.
- `GOOGLE_CLIENT_ID`: OAuth iOS client ID registered for this app's bundle ID.
- `GOOGLE_REVERSED_CLIENT_ID`: reversed client ID callback scheme (for example `com.googleusercontent.apps.123-example`).
- `PRODUCT_BUNDLE_IDENTIFIER`: match the registered iOS application.
- `API_ORIGIN`: keep the `https:/$()/` syntax because `//` otherwise begins an xcconfig comment.

Enable email/password and Google providers in the existing Firebase project. Email verification and password resets use Firebase's configured action URLs. Google sign-in uses the system authentication browser with PKCE, validates OAuth state, then exchanges the Google identity for a Firebase session. Refresh tokens are stored in Keychain with this-device-only protection. Tokens are refreshed before protected requests; verification reload explicitly refreshes the token.

For physical device builds select your Apple development team in Signing & Capabilities. No certificates or credentials are included. App Store distribution still needs the app icon, privacy declarations, signing, screenshots and review. Associated-domain entitlements and universal-link routing are not configured; story share links open the existing website.

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
  -derivedDataPath /tmp/weaware-ios-build CODE_SIGNING_ALLOWED=NO build
```

A simulator SDK build was validated with Xcode 27.1, then installed and launched on an iPhone 17 Pro simulator (iOS 26.2). The live feed loaded articles, images and topics. Public deployed article/topic/podcast payloads were decoded against the Swift models. Firebase identifiers and the Google callback scheme are configured; account-specific operations still need a signed-in test account; Google callback, email delivery, private research access, playback on physical devices and editor approval require end-to-end verification before release. No emails were sent and no research credits or approval actions were consumed during implementation.
