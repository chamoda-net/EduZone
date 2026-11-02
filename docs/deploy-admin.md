# Deploying the platform admin app

The admin app (`frontend/apps/admin`) is EduZone staff's console: teacher applications, organizations, subjects,
users and devices, checkouts, payments, payouts and the audit log. It is deployed **on its own**, separately from
the public web app, and is reachable **only from EduZone's private network** (the VPN). CLAUDE.md section 11
("Platform admin") describes what it does; this file describes where it runs.

## The shape

```
staff laptop ──VPN──► admin app (Next, port 3001) ──private network──► API (FastAPI) ──► Postgres
                       not on the internet                              /api/v1/platform/* only from
                                                                        PLATFORM_ALLOWED_CIDRS
```

Three walls, each enough on its own to stop a stranger:

1. **The admin app is not on the internet.** Give it no public DNS name and no public ingress. Bind it to the
   VPN interface or put it behind a firewall rule that only admits the VPN range.
2. **The API refuses platform routes from anywhere else.** Set `PLATFORM_ALLOWED_CIDRS` on the API to the network
   the admin app's server calls from (its private address or subnet). Every `/api/v1/platform/...` route is a 404
   to any other address. With it empty the API refuses platform routes outside `ENVIRONMENT=local`.
3. **Two-factor sign-in.** An SMS code plus an authenticator code (`scripts/create_platform_admin.py`), a 15-minute
   access token and a 12-hour session that is never extended.

Note on addresses: the API sees the **admin server's** address, not the staff member's, because the browser never
calls the API (the Next server does). So the allowlist names the admin server, and the IP stored in
`audit_logs` for platform actions is the admin server's. Who did it is always recorded (`actor_user_id`).

## Build and run

From `frontend/` (the monorepo root):

```bash
docker build -f apps/admin/Dockerfile -t eduzone-admin .
docker run -d --name eduzone-admin -p 10.8.0.10:3001:3001 -e API_URL=http://10.0.1.20:8000 eduzone-admin
```

(The addresses are examples: publish the port on the VPN-facing address only, and point `API_URL` at the API's
private address.) The image is Next's standalone server (`NEXT_OUTPUT=standalone`, set in the Dockerfile) and runs
as the unprivileged `node` user. Without Docker: `NEXT_OUTPUT=standalone npm run build -w @eduzone/admin`, copy
`apps/admin/.next/static` into `apps/admin/.next/standalone/apps/admin/.next/static`, then
`PORT=3001 API_URL=... node apps/admin/.next/standalone/apps/admin/server.js`.

## Settings

| Where | Setting | Value |
|---|---|---|
| Admin app | `API_URL` | The API's private base URL, e.g. `http://10.0.1.20:8000` |
| Admin app | `PORT`, `HOSTNAME` | `3001`, `0.0.0.0` (defaults in the image) |
| API | `PLATFORM_ALLOWED_CIDRS` | The admin server's address or subnet, e.g. `["10.8.0.10/32"]` |
| API | `ENVIRONMENT` | Anything but `local` in production |

Serve the admin app over **HTTPS** inside the VPN (an internal certificate is fine): its session cookies are
`Secure` and `SameSite=Strict` in production, so a plain-HTTP address won't keep anyone signed in.

## Before the first sign-in

```bash
cd backend && .venv/bin/python scripts/create_platform_admin.py --phone +9477xxxxxxx --name "Staff Name"
```

It prints an authenticator setup link once. Scan it on the staff member's phone; running the script again issues
a new secret and ends that admin's sessions.

## What the app sends

No caching (every page renders per request with the staff member's session), `X-Robots-Tag: noindex`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, no `X-Powered-By`.
