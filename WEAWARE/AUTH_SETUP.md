# WEAWARE authentication setup

The app uses Firebase Authentication for account creation and sign-in. Firebase owns password storage, password-reset emails, Google OAuth, and browser sessions. The API verifies Firebase ID tokens using Firebase Admin SDK; it does not accept profile data supplied by the browser. Apple sign-in is optional and is not shown in the current UI.

## Firebase project setup

1. Create or select a Firebase project and register a Web app.
2. In **Authentication → Sign-in method**, enable **Email/Password** and **Google**.
3. Skip Apple for now. To enable it in a future release, enable **Apple** in Firebase and enter the Apple Developer values Firebase requests. Add `https://<your-firebase-auth-domain>/__/auth/handler` as the return URL for the Apple Services ID.
4. In **Authentication → Settings → Authorized domains**, add `localhost` for development and the deployed website's hostname for production.
5. Copy the Web app's `apiKey`, `authDomain`, `projectId`, and `appId` into `WEAWARE/.env.local`, using `WEAWARE/.env.example` as the template. These are Firebase web-app identifiers, not service-account credentials. Restart Vite after setting them.
6. Set `FIREBASE_PROJECT_ID` on the Cloud Run API to the same Firebase project ID, then deploy the updated backend. Keep the Cloud Run runtime service account and Firebase project consistent with the existing GCP deployment.

## Local development

```sh
cd WEAWARE
cp .env.example .env.local
# Fill in the Firebase Web app values, then:
npm run dev
```

The local Vite proxy forwards `/api/v1/auth/me` to the configured API target. Until the backend with the new endpoint is deployed, Firebase sign-in itself can succeed while API token verification reports unavailable.

## Production checklist

- Set the four `VITE_FIREBASE_*` values in the frontend build environment.
- Set `FIREBASE_PROJECT_ID` on the API service.
- Set `WEAWARE_ALLOWED_ORIGINS` to the website origin so the browser can send the `Authorization` header to the API.
- Deploy the updated API and frontend.
- Confirm Email/Password and Google OAuth in Firebase; verify both from the production hostname. Configure Apple only if it is added to the UI later.

Never put a Firebase Admin service-account private key or Apple private key in frontend environment variables. Firebase web-app config values are expected to be present in the browser; backend verification relies on the Cloud Run service identity.
