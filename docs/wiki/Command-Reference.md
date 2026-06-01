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

