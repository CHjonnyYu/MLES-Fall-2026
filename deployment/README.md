# GCP course service

The production service uses Google Cloud Run in `asia-east1` and a private,
versioned Google Cloud Storage bucket for course edits, account password hashes,
audit entries, and uploaded files. The runtime's local filesystem is not used
as a production database. The service can scale to zero when idle.

`server/app.py` serves the student portal and `/admin/` administration panel.
Administrators manage accounts. Teaching assistants manage weekly progress,
resources, draft/published visibility, file uploads, and links. Public API
responses exclude account records, password hashes, and draft resources.

The bootstrap administrator password is never included in source. Set
`SESSION_SECRET` and `ADMIN_PASSWORD_HASH` through Secret Manager. The initial
administrator is seeded only when the persistent catalog does not yet exist.
Later account changes live in the private catalog and are not reset on deploy.

## Local preview

Install `requirements-web.txt`. Store a random `session_secret` and a
Werkzeug-generated `admin_password_hash` in
`~/.config/mles-course/local-secrets.json` with permission 0600. Then run:

```sh
APP_ENV=development PORT=8766 python server/app.py
```

Local state defaults to `~/.config/mles-course/data/`; it stays outside the
public repository. This preview uses a development HTTP server. Production
uses Gunicorn in the Dockerfile and secure HTTPS session cookies.

## Deploy

```sh
python deployment/deploy.py --project YOUR_PROJECT_ID --initialize
```

The initializer configures a dedicated builder identity, a separate runtime
identity, bucket-scoped object access, and access to two named Secret Manager
values. It does not store a Google service-account key. Use normal application
default credentials on Cloud Run. Existing secrets are retained on redeploy.

After initial deployment, omit `--initialize` for normal updates. The generated
`deployment.json` records the returned production URL and ready revision; it
contains no credential values.

## Editing and recovery

Every write checks the revision shown when the edit form was opened. A stale
form returns HTTP 409 instead of overwriting another assistant's change.
Storage writes also use generation preconditions to handle concurrent instances.
Bucket object versioning preserves previous catalog and upload versions. Restore
an appropriate previous `cms/catalog.json` generation if a course edit needs
recovery. Copy a generation to a separate backup before performing a restore.

## Notebooks and Colab

The prepared notebooks use the public GitHub repository and open directly in
Colab. A newly added GitHub notebook URL automatically gains a Colab link.
Uploaded `.ipynb` files are downloadable from GCP; add a matching public
GitHub-backed Colab URL to provide a direct Colab launch, or use Colab's upload
dialog. The backend does not copy a broad GitHub OAuth token into the cloud.

## Checks

```sh
APP_ENV=development python -m unittest server.test_app -v
```

Tests use a temporary local catalog and test-only passwords. They cover CSRF,
unauthenticated access, role restrictions, disabled-session revocation, draft
visibility, uploads, HTML sandboxing, edit conflicts, login throttling, and
local persistence. Production deployment must additionally confirm Cloud Run
revision readiness, HTTPS cookies, cloud persistence, and the authenticated UI.
