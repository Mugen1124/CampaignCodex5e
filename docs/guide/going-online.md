# Going online

**Optional.** Everything works on your own computer without this. Go online when you want to read your site from another device (a laptop at the table, your phone), or give your players their site — and the live initiative page, the live Party page (each player imports their own character), and each player's private notes that come with it.

The sites go on **Cloudflare**: each is a *Worker* on a free `workers.dev` address, behind **Cloudflare Access**, which asks visitors to sign in with their email (a one-time code is sent to it). Only the emails you allow get in. Cloudflare's free plans cover a typical table — check their current limits if your group is large.

!!! warning "Read this whole page before you start"
    The one thing that matters most: **both sites must sit behind a sign-in.** `publish` checks this after every upload and prints a large WARNING if a site answers without asking for one. Never ignore that warning.

## What you need

- A free **Cloudflare account** (<https://dash.cloudflare.com/sign-up>).
- **Node.js** (<https://nodejs.org>, the LTS version). `publish` uses Cloudflare's own upload tool, *wrangler*, through it.

A *Worker* is Cloudflare's name for a small website or program it runs for you; each of your two sites will be one.

## 1. Sign in once from this computer

Open a terminal in this folder — on Windows, click the folder's address bar in File Explorer, type `powershell`, and press Enter; on a Mac, see the [Quick start](https://github.com/Mugen1124/CampaignCodex5e#quick-start) — and run:

```
npx wrangler login
```

A browser window asks you to allow wrangler into your Cloudflare account.

## 2. Choose your names

In the Cloudflare dashboard, **Workers & Pages** shows your `workers.dev` subdomain (you can set it there the first time). Your sites will be at `https://<worker>.<subdomain>.workers.dev`. Pick two worker names — for example `lantern-coast` and `lantern-coast-players` — and fill them in under `online:` in `campaign.yml`. Leave `enabled: false` for now:

```yaml
online:
  enabled: false                  # true in step 5
  dm_worker: lantern-coast
  players_worker: lantern-coast-players
  subdomain: your-subdomain
  access_team: your-team          # step 3
  players_site: true              # false: only your DM site goes online
```

## 3. Turn on Zero Trust (the sign-in service)

The sign-in comes from Cloudflare's **Zero Trust**. In the dashboard, open **Zero Trust**. The first time, it asks you to:

1. **Choose a team name** — your sign-in page will be `https://<team>.cloudflareaccess.com`. Put that name in `campaign.yml` as `access_team`.
2. **Choose a plan: Free** (up to 50 people). It may ask for a payment method even for the free plan; you aren't charged on it.

Already set up? Your team name is in **Zero Trust → Settings** (the *team domain*).

## 4. Put both sites behind a sign-in

Before the first upload, so neither site is ever public, even for a moment:

1. In the dashboard: **Workers & Pages → Cloudflare Access** (under your account's settings) — turn on Access for **workers.dev**.
2. Scope: **All traffic** — never "Previews only".
3. Policy: **Cloudflare account** (members of your Cloudflare account — you) — never an "Email domain" policy like `gmail.com`, which would let in anyone with Gmail.

This covers **every** Worker on your `workers.dev` subdomain — the players' site too, which stays yours-only until step 6 gives your players their own list.

Cloudflare's menus move around; if the names differ, look for *Access* settings for your workers.dev subdomain.

## 5. Publish

Set `enabled: true` in `campaign.yml`, then run **`publish`**. The first time, it asks you to confirm that step 4 is done; type `yes`. It builds both sites, runs the [leak check](players-site.md#the-leak-check), uploads, and checks that a signed-out visitor is sent to the sign-in. You should see `OK - signed-out visitors to ... get the login page` for each — if you see a WARNING instead, stop and fix step 4 before anything else.

## 6. Let your players in

The players' site gets **its own** sign-in list, separate from yours:

1. **Zero Trust → Access → Applications**: find the application for your players' worker (or add one: *Self-hosted*, its `workers.dev` address).
2. Add a policy, *Allow*, with each player's email (and yours).
3. In `data/party.yml`, give each character their player's `email:` — the same address they sign in with — so the site knows whose card is whose. (Or use **Edit** on the Party page.)
4. Publish again.

Emails stay in `party.yml` and in the players' worker; they're never on any page, and the leak check blocks the upload if one ever turns up there.

## 7. Your key to the players' site: live initiative and players' changes

To show the initiative order on your players' phones, and to bring the changes players make to their cards on the [Party page](players-site.md#the-party-page) into `data/party.yml`, CampaignCodex5e on your computer needs a key to the players' site:

1. **Zero Trust → Access → Service Auth**: create a **service token**. Copy its **Client ID** and **Client Secret** (the secret is shown once).
2. Save them in `tools/tracker-token.txt`, one per line (labels like `CF-Access-Client-Id:` are fine). This file is never published or committed.
3. On the players' application, add a second policy: action **Service Auth**, including that service token.
4. In the initiative tracker (with `CampaignCodex5e` running), tick **Share with players**.

Players see names, initiative, whose turn it is, the round, and conditions — never hit points, AC, or notes. **hide** on a row keeps someone off their list (an ambusher, someone invisible).

With the key in place, **Get players' changes** and **History** appear on your Party page, along with each card's live HP and conditions, the party treasury, and the switch for whether players see each other's current HP — and the tracker starts fights from the party's current HP and keeps the cards up to date. See [the Party page](players-site.md#the-party-page).

## Afterward

The online copies are **read-only**: make changes on your computer with `CampaignCodex5e`, then `publish` again. If `publish` ever prints the big WARNING, open Zero Trust → Access → Applications and check that site's policy before doing anything else.
