# WeAware website

The public WeAware site is a React 18 single-page app built with Vite and Tailwind CSS. It provides the news feed, article reader, The Crosscheck newsletter settings, podcast and audio listening, and the About page. The visual system supports light and dark themes.

## Run locally

```sh
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `http://localhost:8080` by default. Set `VITE_API_BASE_URL` to use another API origin. Copy `.env.example` to `.env.local` and fill in the Firebase web-app values to enable sign-in; Firebase values are public client configuration, never server credentials. See [AUTH_SETUP.md](AUTH_SETUP.md) for the complete setup.

Build and preview the production bundle with `npm run build` and `npm run preview`.

## Main views

- **Home:** Brand introduction and navigation to the product.
- **Feed and reader:** Topic and text filters, published articles, source notes, original links, and article audio.
- **Newsletters:** Preview editions and configure a topic-based daily or weekly email briefing. Saving preferences requires a signed-in, verified email account and explicit consent.
- **Podcasts:** Play published episodes, copy the RSS feed URL, and access the article listening queue. Authorized editors can review podcast drafts from the editorial interface.
- **About:** Explains WeAware's multi-source reading approach, limitations of agreement signals, and ways to read, follow, and listen.

The full published story feed, article reading, article audio, and podcast episodes are available without signing in. Sherlock Mode is experimental and requires a verified signed-in account with pilot access. Newsletter subscriptions and editor-only podcast review continue to use account access where needed.

## Frontend configuration

| Variable | Use |
| --- | --- |
| `VITE_API_BASE_URL` | Optional API origin; omit for same-origin requests and local `/api` proxying |
| `VITE_FIREBASE_API_KEY` | Firebase web app identifier |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase Auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project identifier |
| `VITE_FIREBASE_APP_ID` | Firebase web app identifier |

The API must allow the deployed frontend origin with `WEAWARE_ALLOWED_ORIGINS`. Firebase authorized domains must include the local and deployed hostnames. The backend verifies ID tokens; frontend auth state alone does not authorize account or editorial API access.

## Source layout

- `src/App.jsx` — navigation, feed state, data loading, and view routing.
- `src/components/` — page views, reader, players, newsletter and podcast interfaces.
- `src/auth/` — Firebase setup, auth context, sign-in controls.
- `src/lib/api.js` — API client and response normalization.
- `src/index.css` and `src/theme.js` — visual tokens, global styles, theme behavior.

For article generation and API endpoints, see [`../backend/editorial/README.md`](../backend/editorial/README.md). Audio and podcast infrastructure is documented in [`../backend/audio/README.md`](../backend/audio/README.md); newsletter delivery operations are in [`../backend/NEWSLETTERS.md`](../backend/NEWSLETTERS.md).
