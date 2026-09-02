# Command Reference

Commands work on both channels. On **Telegram** they use inline buttons; on **Zalo** (when `ZALO_ENABLED=true`) the same commands work through numbered-text menus — reply with a number to choose.

## `/today`

Shows today's spending against the daily spending bucket.

Use it after setup to verify the bot replies.

## `/report`

Shows a spending report.

The report supports period and lens controls through Telegram inline buttons:

- Week
- Month
- Quarter
- Year
- Account lens
- Category lens

## `/accounts`

Lists tracked accounts and account management actions.

Common flows:

- Add a new account.
- Assign old unmapped transactions to an account.
- Review account names and source routing.

## `/manage`

Manages categories.

Use it to:

- Add categories.
- Rename categories.
- Delete categories.
- Edit bucket amounts.

## `/keywords`

Manages auto-categorization rules.

Example:

```text
GRAB -> Daily Spending
Spotify -> Subscription
```

When a new transaction matches a keyword rule, the bot can categorize it without asking.

## `/allocate`

Sets or edits monthly budget allocations by category.

First use opens the setup flow. Later uses open edit mode so you can change one bucket at a time.

## `/recat <row>`

Re-categorizes a past transaction by its sheet row number, e.g. `/recat 125`. It uses that transaction's own month, so older rows show the correct buckets.

You can also fix the *just-logged* transaction by tapping the "🔄 Sai mục?" button on its confirmation (Telegram). On Zalo, an uncategorized expense is categorized by replying with the bucket number from the picker menu.

## `/cashback`

Tracks credit-card cashback per card, using MCC-based rules.

- `/cashback` — overview: earned, caps, per-MCC breakdown for the current cycle.
- `/cashback templates` — list the built-in card templates.
- `/cashback seed <template> [card]` — apply a template to one of your cards.
- `/cashback setup [card]` — wizard for a card no template covers: rate, cap, gate, cycle, then MCC rules.
- `/cashback export [card]` — dump the card's config as YAML.
- `/cashback savetemplate [card]` — save the card's config as a reusable template.

Templates live in `card_templates/` as YAML. Adding a card for a bank nobody has covered yet is a pull request, not a code change.

## `/pending`

Lists transactions that arrived while you were in the middle of another flow and shows the category picker for them. Nothing is lost when a bank notification interrupts you mid-command.

## `/transfer` and `/cc pay`

Records money you moved yourself: `/transfer` between two of your accounts, `/cc pay` for a credit-card payment. Neither counts as spending.

## `/lang`

Switches the bot's language between Vietnamese and English.

## `/help` and `/start`

Shows the command list. `/cancel` aborts whatever flow is half-finished.

## Amount shorthand

Anywhere the bot asks for an amount you can type `500k`, `3tr`, `3tr5`, or `1m2` instead of the full number.
