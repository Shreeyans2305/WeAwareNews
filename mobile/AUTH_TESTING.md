# Test mobile accounts

Both apps use the website Firebase project `weaware-3504c` and existing website accounts. Email/password and Google providers are enabled. No administrator credentials or OAuth client secrets are included in the apps.

## Configuration

- Android package: `news.weaware.weaware`. This Mac’s debug SHA-1/SHA-256 are registered. Google Services reads `android/app/google-services.json`; no Firebase build flags are needed.
- iOS bundle: `news.weaware.ios`. `Config.xcconfig` contains the public API key, iOS OAuth client and reversed callback scheme, sourced from the downloaded `GoogleService-Info.plist`.

## Try the account features

1. Open Account and use your website email/password, or select Continue with Google and complete Google’s login yourself. Use your website Google account to keep the same profile and preferences.
2. For a new email/password account, open the verification email, then select Refresh verification on Android or I have verified my email on iOS.
3. Open Crosscheck to load and save your topic/frequency preferences. Subscription and test-email buttons send real email.
4. Open Sherlock to view your research history and eligibility. Signing in does not grant invitations, credits, or editorial permissions. Starting an investigation uses an available credit.
5. Sign out and confirm private data disappears. Sign in on the other platform to check the same account and preferences load.

The iOS Google flow was checked through Google’s login screen; Android Firebase initialization succeeded. Full authentication and private feature checks require you to finish signing in. No passwords were entered, test users created, email sent, or research credits used during configuration.

For another development Mac, register its Android debug signing fingerprints in Firebase. Before distribution register production signing fingerprints, configure Apple signing, and complete physical-device testing. Configuration follows [Firebase’s Android setup](https://firebase.google.com/docs/android/setup) and [Google’s iOS client/callback setup](https://developers.google.com/identity/sign-in/ios/start-integrating).
