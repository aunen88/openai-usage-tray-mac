# OpenAI Usage Tray

A macOS menu bar app that shows your OpenAI API token usage and costs at a glance — per model, for today and the current billing month.

## What it shows

- **Today** and **this month** total cost (USD) and token counts (input / output)
- **Per-model breakdown**: cost and tokens for each model you've used
- Spend warning (⚠) and critical (🔴) indicators when monthly spend exceeds your thresholds
- Updates every 5 minutes (configurable)

> **Note:** Per-model costs are derived by multiplying your token counts by a hardcoded pricing table in `api.py`. Costs for models not in the table show `—`. Update the `PRICING` dict in `api.py` if OpenAI changes prices.

> **Timezone note:** Token counts use local midnight for the "today" window. Cost totals use UTC midnight (API limitation). Near UTC midnight, today's tokens and cost may briefly show different periods.

## Requirements

- macOS 12+
- An [OpenAI Admin API key](https://platform.openai.com/api-keys) with **Usage: Read** permission

## Getting an Admin API key

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **Create new secret key**
3. Under **Permissions**, select **Usage: Read**
4. Copy the key — you'll only see it once

## Installation

1. Download `OpenAIUsageTray.app` from the [Releases](../../releases) page
2. Drag it to your **Applications** folder
3. Double-click to open — if macOS blocks it, go to **System Settings → Privacy & Security** and click **Open Anyway**
4. A `?` icon appears in your menu bar — click it, then choose **Settings**
5. Paste your Admin API key and click through the prompts

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| API Key | — | Your OpenAI Admin API key (`usage.read` scope) |
| Refresh interval | 300s | How often to poll (60–600 seconds) |
| Warning threshold | $50 | Monthly spend that turns the icon ⚠ |
| Critical threshold | $100 | Monthly spend that turns the icon 🔴 |

## Building from source

```bash
git clone https://github.com/aunen88/openai-usage-tray-mac.git
cd openai-usage-tray-mac
pip install -r requirements.txt
sh build.sh
```

The built app will be at `dist/OpenAIUsageTray.app`.

## Running tests

```bash
pytest -v
```

Note: `rumps` is macOS-only. Tests for `api.py`, `config.py`, and `menu_builder.py` run on any platform using mocks. `main.py` requires macOS.
