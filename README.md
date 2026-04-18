<div align="center">

# telegram-finance-tracker

Self-hosted Telegram bot for tracking personal income and expenses, with cash vs. transfer balance and automatic reports.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.x-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://github.com/python-telegram-bot/python-telegram-bot)
[![License](https://img.shields.io/badge/License-MIT-6B7280?style=flat-square)](LICENSE)

</div>

---

## Setup

```bash
git clone https://github.com/your-username/telegram-finance-tracker.git
cd telegram-finance-tracker
cp .env.example .env   # fill in your values
./setup.sh
```

**Required in `.env`:**

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | From [@userinfobot](https://t.me/userinfobot) |
| `HOST_DATA_DIR` | Host path where `finance.db` will be stored |
| `CURRENCY_SYMBOL` | e.g. `฿` `$` `₭` (default: `฿`) |

---

## Features

- **Expense & Income** tracking with category selection
- **Cash / Transfer** split — separate running balance per method
- **Auto-cancel** — pressing any menu button mid-flow cancels the current action and processes the new one
- **Delete Last** — remove the most recent transaction with confirmation
- **Custom categories** — add/remove per type from within the bot
- **Automatic reports** — daily at 23:30, monthly on last day, yearly on Dec 31 (Bangkok time)
- **On-demand reports** — Today, This Month, This Year, All-Time Summary
- **Single-user** — restricted to one Telegram Chat ID

---

## Docker

```bash
docker compose logs -f     # logs
docker compose down        # stop
docker compose up -d --build  # rebuild
```

---

## License

[MIT](LICENSE)
