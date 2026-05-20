# Discord Standup Integration — Setup Runbook

> Founder UI work. Webhook URL is secret — never commit to repo.

1. Discord: Server Settings → Integrations → Webhooks → New Webhook for `#mmw-dev`. Copy URL.
2. Linear: Settings → Integrations → Slack/Discord → paste webhook URL. Select team + channel.
3. Daily digest: enable, time 9:00 AM (Asia/Ho_Chi_Minh), filter "Active cycle".
4. Weekly digest: enable Monday 9:00 AM, project = each phase OR overall.
5. Verification: Linear → trigger manual digest → confirm message appears in #mmw-dev.
6. Rotation: webhook URL is secret — store Linear-side, NOT in repo. Rotate every 6 months.
