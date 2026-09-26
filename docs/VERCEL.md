# Vercel demo hosting

The React dashboard and its narrow API relay run on Vercel. The existing Python services, AWS Bedrock integration and Twilio phone calls continue running on the presenter’s laptop. Keep those services and the HTTPS tunnel running. This is a hosted dashboard with a temporary backend, not an independent cloud deployment of the phone service.

## Configuration

The dashboard opens without an access code. The gateway only forwards the required read/search/accept routes. Internal dialing, results and storage endpoints stay inaccessible.

From `apps/dashboard`, link the desired Vercel project and deploy a preview with:

```sh
vercel deploy --yes --target preview \
  --build-env VITE_ORCHESTRATOR_URL=/api \
  --build-env VITE_COLLECTOR_WS= \
  --env UZIMA_BACKEND_URL=https://YOUR-CALLBACK-HOST
```

Only the callback origin is stored on Vercel. AWS and Twilio credentials remain on the backend. Hosted updates use the existing one-second status poll instead of a WebSocket server.

The callback host must match the existing tunnel. If the tunnel URL changes, update the backend’s callback/ticket settings and deploy again with the new origin. Existing in-memory transfers and tickets are lost if their services restart.

Vercel’s deployment protection may additionally require the project owner to sign in. Share the preview according to the project’s access settings.

## Verification

- `make test`
- `node --test apps/dashboard/tests/relay.test.mjs`
- Build with the two `VITE_` settings above.
- Verify the tunnel’s `/dashboard/health` responds without an access code.
- Deployment readiness is reported by the Vercel CLI. A live phone rehearsal requires the configured demo participants to be ready.
