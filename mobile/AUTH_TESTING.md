# Test mobile accounts

Both apps use the website Firebase project `weaware-3504c` and existing website accounts. Email/password and Google providers are enabled. No administrator credentials or OAuth client secrets are included in the apps.

## Configuration

- Android package: `news.weaware.weaware`. This Mac’s debug SHA-1/SHA-256 are registered. Google Services reads the ignored local `android/app/google-services.json`; no Firebase build flags are needed.
- iOS bundle: `news.weaware.ios`. Ignored `Config.local.xcconfig` supplies the restricted API key, iOS OAuth client and reversed callback scheme. Copy its `.example` template for a new checkout.

## Try the account features

1. Open Account and use your website email/password, or select Continue with Google and complete Google’s login yourself. Use your website Google account to keep the same profile and preferences.
2. For a new email/password account, open the verification email, then select Refresh verification on Android or I have verified my email on iOS.
3. Open Crosscheck to load and save your topic/frequency preferences. Subscription and test-email buttons send real email.
4. Open Sherlock to view your research history and eligibility. Signing in does not grant invitations, credits, or editorial permissions. Starting an investigation uses an available credit.
5. Sign out and confirm private data disappears. Sign in on the other platform to check the same account and preferences load.

The iOS Google flow was checked through Google’s login screen; Android Firebase initialization succeeded. Full authentication and private feature checks require you to finish signing in. No passwords were entered, test users created, email sent, or research credits used during configuration.

For another development Mac, register its Android debug signing fingerprints in Firebase. Before distribution register production signing fingerprints, configure Apple signing, and complete physical-device testing. Configuration follows [Firebase’s Android setup](https://firebase.google.com/docs/android/setup) and [Google’s iOS client/callback setup](https://developers.google.com/identity/sign-in/ios/start-integrating).

## Configuration protection

Live platform configs stay local; templates are committed. Run `python3 mobile/scripts/check_config.py --staged` before committing. CI checks tracked mobile files for credential literals and accidentally tracked live config files. Client keys remain embedded in compiled apps: application and API restrictions are the primary protection, not Git ignore rules. The exposed iOS key was replaced; rebuild installed apps after rotation. Passwords and OAuth client IDs do not change.

Run the iOS request regression checks with:

```sh
swiftc mobile/ios/WeAware/API.swift mobile/ios/Tests/main.swift -o /tmp/weaware-auth-tests
/tmp/weaware-auth-tests
```

## Rotation validation (2026-10-29)

- Replacement iOS key restricted to `news.weaware.ios`, Identity Toolkit and Secure Token APIs.
- Live requests with the correct bundle header reach token validation; wrong or missing bundle headers are rejected with `API_KEY_IOS_APP_BLOCKED` on both services.
- Deleted previous key is rejected with `API_KEY_INVALID` on both services.
- Swift request regression checks, iOS simulator build, Flutter analysis and four Flutter tests passed. Both platforms also build without local configs.
- Configured builds installed and launched on Android and iOS simulators; public feed smoke checked and Android Firebase initialization confirmed.
- Full Google/email account sign-in and private account actions still require a test account. No passwords, emails, research credits, or editorial actions were used for this security check.

The revoked iOS key was subsequently redacted from all reachable Git history on both remote branches. All remaining objects in the rewritten repository were scanned for the leaked value, and current branch-tip files were verified unchanged. GitHub secret-scanning alert #1 was resolved as revoked. Other clones should be freshly cloned to avoid restoring old history; cached GitHub commit views may require GitHub Support cleanup.

## iOS session persistence fix (2026-10-29)

The Google flow reached Firebase successfully, but the unsigned simulator build had no application identifier entitlement. Simulator securityd rejected Keychain writes with `-34018`; the Account screen therefore stayed signed out after Google completed. Simulator builds now use signing (`CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=-`). Authentication validates the profile and persists the refresh token before publishing signed-in state; restore and refresh errors are handled explicitly.

Eight hosted authentication tests passed on iOS 26.5, including real Keychain round trips, a simulated Google callback with real secure persistence and profile restoration, failed secure saves, invalid callback state, missing profiles, offline refresh and invalid refresh tokens. Tests also passed without live Firebase configuration. Create-account and sign-in forms were checked in the simulator. Live user sign-in after this fix still needs the user to complete Google's credentials; no production test accounts were created.
