# AI & Science news digest

A short Python script that reads the day's science and AI news for you. It pulls stories from
29 RSS feeds, asks an AI to score each one against a rubric you write, and emails you the best
ones every morning.

**Just want the rubric? [It's here.](rubric.md)** That file is the interesting part — the code
is only plumbing.

---

## How it works

1. **Fetch.** The script checks 29 RSS feeds — journals, preprint servers and science news
   sites — and keeps anything published in the last day. Duplicates are removed, and arXiv
   preprints are filtered down to ones touching health, fairness, safety and similar topics,
   since those feeds are enormous.
2. **Score.** Stories are sent to Claude in batches of 30, along with the whole of
   [rubric.md](rubric.md). The rubric says who the audience is, how to sort stories into four
   strands, what makes a story worth covering, and which kinds of story can't score above 5.
   Claude returns a score out of 10 for each story, plus a plain-English summary, a one-line
   angle, and a short explanation of how the science works.
3. **Select.** The top 12 stories scoring 7 or more are kept. If a whole strand would
   otherwise be missing, its best story is added back as long as it scored at least 6.
4. **Send.** The selection is emailed to you as a formatted digest, and saved as a Markdown
   file in `digests/` so you have an archive.

The whole run takes a couple of minutes.

## What you need

- **Python 3.9 or newer.** Check with `python3 --version`.
- **[Claude Code](https://claude.com/claude-code)**, installed and logged in. Scoring runs
  through the Claude Code command-line tool in headless mode (`claude -p`), which uses your
  logged-in Claude subscription rather than pay-per-token API credits. There is no
  `ANTHROPIC_API_KEY` to set up. Run `claude` once on its own first and log in, so the script
  isn't the thing discovering you're logged out.
- **A [Resend](https://resend.com) account**, for sending the email. The free tier is plenty.
  Resend gives you `onboarding@resend.dev` to send from while testing; sending from your own
  domain means verifying it with them first.

## Setup

```bash
# 1. Get the code
git clone https://github.com/clairecoffey/ai-news-digest.git
cd ai-news-digest

# 2. Make a virtual environment (keeps these packages separate from the rest of your system)
python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# 3. Install the three packages it needs
pip install -r requirements.txt

# 4. Create your own settings file and open it in an editor
cp .env.example .env
```

Fill in `.env`. At minimum you need `RESEND_API_KEY`, `FROM_EMAIL` and `TO_EMAIL`. Every
setting is explained in the file, and the rest have sensible defaults.

`.env` holds your keys. It is already listed in `.gitignore`, so it won't be committed if you
push your own copy — keep it that way.

## Running it

```bash
# Fetch and score, print the results, but send no email — good for testing
python run.py --dry-run

# The real thing
python run.py
```

A dry run still writes the Markdown archive to `digests/`, so you can read the output without
anything landing in your inbox.

## Running it every morning

On Mac or Linux, `cron` can run it on a schedule. Open your crontab:

```bash
crontab -e
```

and add one line, which runs it at 8am daily:

```
0 8 * * * cd /path/to/ai-news-digest && .venv/bin/python run.py >> digest.log 2>&1
```

Replace `/path/to/ai-news-digest` with wherever you put the folder. The `>> digest.log` part
saves the output so you can see what happened if an email doesn't arrive.

Two things worth knowing: your computer has to be awake at that time for cron to fire, and
cron runs with a bare environment, so use the full path to the Python inside `.venv` as above.

## Making it yours

**The rubric.** Edit [rubric.md](rubric.md). The entire file is sent to the AI with every
batch of stories, so editing it is how you change what gets picked — no code changes needed.
Rewrite the audience description, change the strands, add your own scoring caps. If you rename
a strand, also rename it in the `STRANDS` list at the top of `digest/scorer.py`, which just
holds the display names used in the email.

**The feeds.** Edit the `FEEDS` list at the top of `digest/feeds.py`. It's a list of names and
RSS addresses; add or delete lines. Most publications have an RSS feed somewhere, often at
`/feed` or `/rss`.

**How much you get.** `MIN_SCORE` and `TOP_N` in `.env` control how strict and how long the
digest is.

## If something goes wrong

- **"Missing environment variable"** — you haven't created `.env`, or a required value is blank.
- **"claude CLI exited 1"** — Claude Code isn't installed, isn't on your PATH, or you're logged
  out. Run `claude` on its own to check, and set `CLAUDE_BIN` in `.env` if it's installed
  somewhere unusual.
- **A few feeds fail** — normal. Feeds go down; the script prints which ones failed and carries
  on with the rest.
- **No email arrives** — check your Resend dashboard for the delivery, and your spam folder.

## A note on this project

This is a personal project, shared as-is because people asked to see it. It's built around my
taste in science stories and my own setup, and I'm not able to offer support, review pull
requests or fix problems for anyone else. Fork it and make it yours — that's the point of the
rubric living in its own file.

MIT licensed. See [LICENSE](LICENSE).
