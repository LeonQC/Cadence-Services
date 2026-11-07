# GitHub App integration

This TodoApp uses a GitHub App installation, not a personal access token. The
app creates a short-lived App JWT, exchanges it for an installation access
token, and uses that token to verify the repository selected in Settings.

## Create the GitHub App

In GitHub, open **Settings → Developer settings → GitHub Apps → New GitHub
App**. Configure:

- App name: any available name; its URL slug becomes `GITHUB_APP_SLUG`.
- Setup URL: `http://localhost:8000/settings/integrations/github/callback`.
- Repository permissions: **Metadata: Read-only**. Add **Issues: Read and
  write** and **Pull requests: Read-only** when sync is enabled.
- Install the app on the account that owns the repository.
- Generate a private key and keep the downloaded PEM file outside the repo.

The official GitHub quickstart also describes webhook proxying through Smee.io
for local development. This first integration step uses the setup callback and
REST API; webhook synchronization can be added after event permissions are
decided.

## Configure localhost

Add these values to `.env`:

```text
GITHUB_APP_ID=123456
GITHUB_APP_SLUG=your-app-slug
GITHUB_PRIVATE_KEY_PATH=C:\path\to\your-app.private-key.pem
GITHUB_SETUP_URL=http://localhost:8000/settings/integrations/github/callback
```

Restart FastAPI, open **Settings → Integrations → GitHub**, install the app,
then enter the repository as `owner/repository`. The app verifies access before
storing the canonical repository name.

The database stores only the GitHub installation id and repository name. The
private key and one-hour installation tokens are never stored in SQLite.

## Link commits to TodoApp issues

The app also accepts GitHub `push` webhooks at:

```text
http://localhost:8000/github/webhook
```

Set a long random value as `GITHUB_WEBHOOK_SECRET` in `.env`, and enter the
same value in the GitHub App's Webhook secret field. Enable the `Push` event
and give the App at least **Contents: Read-only** permission. GitHub signs the
raw request body with `X-Hub-Signature-256`; the receiver verifies that
signature before processing it.

For localhost, create a channel at Smee.io and set the GitHub App's Webhook
URL to the Smee URL. Run the proxy in a second terminal:

```text
npx smee -u YOUR_SMEE_URL -t http://localhost:8000/github/webhook
```

When a pushed commit message or branch contains an issue identifier such as
`TODO-3`, the push handler links that commit to the matching TodoApp issue.
The linked commits appear in the issue's `Diffs` section and open the commit
on GitHub when clicked.
