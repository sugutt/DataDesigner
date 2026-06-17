# Synthetic Data Studio Frontend

Next.js frontend for the production Synthetic Data Studio.

```bash
npm install
npm run dev
```

Set:

```bash
STUDIO_API_BASE=http://localhost:8000
STUDIO_ADMIN_TOKEN=dev-token
```

The browser talks to the Next.js proxy under `/api/studio/*`; the bearer token stays server-side.
