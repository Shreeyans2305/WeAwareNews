# WeAware mobile apps

Two independent mobile clients share the website's existing FastAPI service and Firebase accounts:

- `android_flutter/`: Flutter application targeting Android.
- `ios/`: SwiftUI application for iOS and Xcode.

These are native mobile screens, with platform navigation and playback, rather than embedded copies of the website. Each app has its own setup and validation instructions in its directory.

## Backend and account configuration

The default API origin matches `WEAWARE/src/lib/api.js`: `https://weaware-api-777322408950.us-central1.run.app`. Override it using each app's configuration when developing against another backend. A phone's `localhost` points to the phone; use an address reachable from the device for a local backend.

Both apps are registered in the website’s Firebase project, **`weaware-3504c`**, so they share accounts and preserve newsletter and Sherlock ownership. Live client configurations are local ignored files; committed templates document setup. Android debug signing fingerprints for this Mac are registered. If moving to another Firebase project, register Android and iOS applications in that same project. Match the registration's package/bundle identifiers to the app targets. Download the platform configuration from Firebase and follow each client README. Firebase client identifiers are not administrator credentials; never put service-account keys or server secrets in either application.

Enable Email/Password and Google providers in Firebase Authentication. Google sign-in also requires the Android signing certificate fingerprints and the iOS reversed-client-ID URL scheme. Use a dedicated test account for authenticated checks; no existing subscriber preferences or editorial approvals should be changed simply to validate a build.

## Website feature contract

| Capability | Existing backend contract |
| --- | --- |
| News, topics, search, pagination | `GET /api/v1/topics`, `GET /api/v1/articles?topic=&q=&limit=&offset=` |
| Full article, consensus, source notes, flagged claims | `GET /api/v1/articles/{id}` |
| Article narration and queued status | `GET` and `POST /api/v1/articles/{id}/audio` |
| Reviewed podcasts and source links | `GET /api/v1/podcasts/episodes`; RSS at `/podcasts/feed.xml` |
| Account identity | Firebase sign-in, refreshed ID token; `GET /api/v1/auth/me` |
| Newsletter preferences | Authenticated `GET` and `PUT /api/v1/newsletters/preferences` |
| Unsubscribe | Authenticated `POST /api/v1/newsletters/preferences/unsubscribe` |
| Sherlock eligibility and credits | Authenticated `GET /api/v1/sherlock/entitlement` |
| Sherlock research and history | Authenticated `GET` and `POST /api/v1/sherlock/requests`, `GET /requests/{id}` |
| Sherlock cancellation and PDF | Authenticated `POST /api/v1/sherlock/requests/{id}/cancel`, `GET /requests/{id}/report.pdf` |
| Podcast editorial review | Authenticated `GET /api/v1/editorial/podcasts/drafts`, `POST /drafts/{id}/approve` |
| Story sharing | System share sheet with `https://weaware.news/s/{id}` |

Private calls use `Authorization: Bearer <Firebase ID token>`. The backend remains the authority for verified-email requirements, editor allowlists, pilot eligibility, credits, and request status. Newsletter writes require explicit consent and valid published topics. Sherlock creation uses a stable submission key for retries; completed reports and PDFs are available only after the backend's editorial gate.

The website's friend-to-friend activity feed is explicitly a frontend mock and has no delivery API. Video generation is an operational pipeline, not a public website viewing feature. Neither should be presented as a working mobile service.

## Discover

Android has a Discover tab; iOS opens Discover from the cards button on News. Swipe left to skip or right to save. Both offer explicit buttons, undo, a saved library, source agreement, source evidence and full reporting. Cards show up to three verbatim sentences from the article body (summary fallback), preserving attribution and uncertainty. They do not generate new factual claims. Saved stories and decisions persist on this device separately for each account and guest; they do not sync between platforms or change the server feed ranking.

## Manual acceptance checks

1. Launch without Firebase configuration: public news and podcasts remain available, and sign-in explains the required setup.
2. Browse topics, search, clear the search, refresh, open an article, inspect original sources and flagged claims, and share its canonical website link.
3. Compare guest preview behavior with a signed-in account; load additional news after signing in.
4. Play a reviewed podcast; pause, seek, and switch tracks. Request article narration and handle queued, unavailable, and failed states honestly.
5. Register or sign in, reset a password, verify email, refresh account state, and sign out. Confirm private information disappears on account changes.
6. Save daily/weekly newsletter preferences with explicit consent, reopen them, and unsubscribe using a test account.
7. For an entitled verified test account, submit a specific research question with brief/standard/detailed length, inspect processing status/history, cancel an eligible request, and open a completed report with evidence and PDF sharing.
8. Test editorial actions only with an authorized editor and an intentionally prepared test draft; approval initiates real audio work.
9. In Discover, save and skip cards, undo, reopen Saved after an app restart, inspect evidence and confirm a different account has its own library.
10. Check light/dark appearance, larger system text, small screens, network failure, empty results, and re-entry after backgrounding.

## Release work

Local builds do not establish production readiness. Before publishing, configure final application identifiers and signing, verify Google sign-in on physical devices, complete authenticated acceptance checks, supply store icons/screenshots and privacy disclosures, and test audio behavior on real devices. Universal Links/App Links require website association files and verified domains before links can reliably open installed applications.
