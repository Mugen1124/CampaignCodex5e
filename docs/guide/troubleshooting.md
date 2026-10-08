# Troubleshooting

## Setup

**"Python not found" (Windows).** Setup installs Python with `winget`. If that isn't available, install Python 3.12 from <https://www.python.org/downloads/> with **Add python.exe to PATH** ticked, then run `setup.bat` again. If a window says Python was installed but can't see it, close it and run setup again.

**"Couldn't create .venv" (Linux).** Install the venv module: `sudo apt install python3-venv` (Debian/Ubuntu), then `./setup.sh` again.

**macOS: "permission denied" running a script.** Make them runnable once, in Terminal in this folder: `chmod +x *.sh *.command`. Or run them with `bash`, which always works: `bash setup.sh`. If macOS won't open the `.command` file ("unidentified developer"), open **System Settings → Privacy & Security**, scroll down, and choose **Open Anyway** next to its name.

## Starting the site

**A box about "MkDocs 2.0" appears when the site starts.** It's a notice from Material for MkDocs about a future version. CampaignCodex5e stays on MkDocs 1.x (see `requirements.txt`), so it doesn't affect you — ignore it.

**The page doesn't open, or says the address is in use.** Another `CampaignCodex5e` is already running — close its window, or use that one. The site is at <http://127.0.0.1:8000>.

**Saving doesn't work (Edit, the encounter builder, the recorder).** Those need the save helper, which `CampaignCodex5e` starts. Check the `CampaignCodex5e` window is still open, then reload the page.

**A change to a file in `hooks/` doesn't show.** Close the `CampaignCodex5e` window and start it again; pages and data reload by themselves, the engine doesn't.

## Warnings in the CampaignCodex5e window

They're there to help, and the site still builds. The common ones:

| Warning | Means |
|---|---|
| `Unknown mention [[...]]` | a name in brackets that's not in your data — a typo, or someone to add |
| `Unknown monster id` / `encounter id` / `map id` | a marker pointing at something that doesn't exist |
| `... is missing: hook` | a required field left out of a data entry |
| `Similar NPC names` | two names easy to confuse at the table; if it's on purpose, add the pair to `data/checks.yml` |
| `Map '...': source not found` | `data/maps.yml` points at a file that isn't in your maps folder |
| `Could not read ....yml` | a YAML mistake in that file — usually indentation, or text with a colon that needs quotes |

## The players' site

**The leak check blocks publishing.** It lists exactly what it found and where. Usually it's a secret repeated in public text, or a DM-only fact quoted on a session page; hide the text (a DM box, `<!-- players: hide -->`) or reword it, and run `codex check` again.

**Someone isn't showing on the players' site.** They appear once they're `[[mentioned]]` in the public part of a session page, or listed under `reveal:` in `data/revealed.yml`. A `revealed: false` in their data overrides both.

## Going online

**publish says wrangler/Node isn't installed.** Install Node.js (LTS) from <https://nodejs.org>, open a new terminal, and run `npx wrangler login`.

**publish prints a big WARNING that a site answered without a sign-in.** Stop and fix it: in Cloudflare's Zero Trust → Access → Applications, check that site's application and policy (see [Going online](going-online.md)), then publish again and confirm you see `OK - signed-out visitors ... get the login page`.

**Share with players says the token wasn't accepted.** Check `tools/tracker-token.txt` (Client ID, then Client Secret) and that the players' application has a **Service Auth** policy including that token.

## Getting your old version back

`codex backup` zips sit in the `<folder>-backups` folder next to this one; the newest 20 are kept. Open one and copy back the files you need — nothing is overwritten automatically. With git, `git log` and `git restore` do the same.
