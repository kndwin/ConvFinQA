# ConvFinQA infrastructure

The committed definitions target Railway project `hospitable-insight`
(`97155b4d-6e91-45e6-b6b8-1ea9d826ff06`), production environment
(`593ee8c0-fef1-44ee-8d62-baa0bdd59aa9`), and service `ConvFinQA`
(`af5d52f2-67d2-4f7a-8bf8-92f161707ff4`). They use GitHub repository
`kndwin/ConvFinQA` on branch `main`. The Railway CLI must be authenticated and
linked to that project/environment, and Railway must have access to the GitHub
repository.

## Railway

```sh
cd infra
pnpm install
railway login
railway link --project 97155b4d-6e91-45e6-b6b8-1ea9d826ff06 --environment production
pnpm railway:plan
pnpm railway:apply # only after reviewing the plan
```

`OPENAI_API_KEY` is intentionally not in this repository. `preserveExisting`
does not provide a guarantee when the variable is currently unset, so the key
must already exist in Railway before applying this configuration; the first
plan is therefore not proof that apply is ready. If it needs to be seeded,
read the existing local `server/.env` without printing it (from `infra`):

```sh
python3 - <<'PY' | railway variable set OPENAI_API_KEY --stdin --skip-deploys \
  --service ConvFinQA --environment production
from pathlib import Path

for line in Path("../server/.env").read_text().splitlines():
    if line.startswith("OPENAI_API_KEY="):
        value = line.split("=", 1)[1].strip()
        if not value:
            raise SystemExit("OPENAI_API_KEY is empty")
        print(value, end="")
        break
else:
    raise SystemExit("OPENAI_API_KEY is missing")
PY
```

Never commit `server/.env` or put its contents in Pulumi/Railway source files.
The Railway service deploys from committed and pushed `main`; local changes
alone are not deployed.

## Cloudflare Pages

The Pages target is account `d549a47e154c5803519d3c312cfa6d1c`, project
`convfinqa`, with GitHub repository ID `1334933457` and account owner ID
`22161029`. Install and authenticate Pulumi (including a Pulumi Cloud access
token or a configured self-hosted backend), and authenticate Cloudflare with a
token that can manage Pages for that account (or the equivalent
`CLOUDFLARE_API_TOKEN`/account configuration).

```sh
cd infra
pnpm install
pulumi login
pulumi stack select convfinqa   # create/select the intended stack first
pulumi config set backendUrl https://<railway-service-domain>
pnpm cloudflare:preview
pnpm cloudflare:up                # only after reviewing the preview
```

`backendUrl` is required and becomes the frontend `VITE_API_BASE_URL` for
preview and production. Do not run either apply command until credentials,
the Railway key prerequisite, and the committed/pushed `main` source are
ready.
