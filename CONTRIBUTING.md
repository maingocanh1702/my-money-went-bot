# Contributing

Contributions are welcome — issues, pull requests, forks.

Be opinionated about scope: this bot is intentionally minimal. Features outside
the roadmap in the README are unlikely to be merged, but are worth discussing
in an issue first, before you spend an evening on them.

## Getting set up

```bash
pip install -r requirements-dev.txt   # runtime + test dependencies
pytest tests -q
```

The suite runs entirely against an in-memory `FakeSpreadsheet` — no Google API
calls, no credentials, no network. If a test of yours needs either, it is
testing the wrong thing.

You do not need a deployed bot to contribute. You do need one to test a real
webhook end to end; see the
[wiki](https://github.com/maingocanh1702/my-money-went-bot/wiki) for setup.

## Pull requests

- **Include tests for new behavior.** Money moves through this code; a change
  nobody can regress against will not survive the next refactor.
- **Match the existing style** — functional helpers, docstrings that say *why*,
  no speculative abstraction.
- **For UX changes, attach a screenshot** of the Telegram or Zalo message.
- **Keep secrets out.** Never put a real token, URL or secret in a test fixture
  or in `google_apps_script.js`. Push protection is on and will stop the
  obvious cases, but it will not catch a random-looking string.
- Both language versions of a user-facing string live in `i18n/vi.py` and
  `i18n/en.py`, and a test enforces that their keys match. Add both.

## Adding a cashback card

The most useful contribution, and the one that needs no Python: cards are
YAML templates in `card_templates/`, not code.

```bash
python card_templates/validate.py card_templates/your_card.yaml
```

Start from `cake_freedom.yaml` or `techcombank_visa.yaml`, or let the bot write
one for you — configure the card with `/cashback setup`, then `/cashback
export` prints the YAML. Send it as a pull request so the next person with that
card does not have to work the rules out again.

## Documentation

The wiki is published from `docs/wiki/` by a workflow on every push to `main`.
Edit the files here and open a pull request; editing the wiki directly gets
overwritten.

## The autopilot directories

`scripts/autopilot-*`, `scripts/ap-*`, `scripts/codex-review-pin.sh` and
`docs/autopilot-*` are the maintainer's agent-assisted review harness. They are
not part of the bot, are not needed to run it, and you can ignore them entirely
when contributing.
