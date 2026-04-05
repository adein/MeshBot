# MeshBot

A plugin-based Meshtastic bot written in Python. MeshBot connects to a Meshtastic node over Serial or TCP and responds to user commands on the mesh network.
It includes an interactive terminal dashboard for administration.

## Features

- **Plugin architecture** — commands, modules, and services are independently configurable and can be enabled/disabled without restarting
- **Interactive admin dashboard** — terminal UI built with [Textual](https://textual.textualize.io/) with a live log view and admin console
- **Scheduled modules** — push NWS weather alerts, firmware update notifications, and app release notifications to mesh channels automatically
- **Node database** — tracks nodes heard on the mesh with location, hardware, and activity data
- **DM-only mode** — individual modules can be restricted to respond only to direct messages

## Requirements

- Python 3.10+
- A Meshtastic node with the Serial or TCP interface enabled
- A [Positionstack](https://positionstack.com/) API key (free tier available) — required for weather and location-based commands
- A [GitHub](https://github.com/settings/tokens) personal access token — optional, required only for firmware/app update monitoring modules

## Installation

```bash
git clone https://github.com/adein/MeshBot.git
cd MeshBot
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your settings (see [Configuration](#configuration) below), then run:

```bash
python main.py
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and fill in the values. The `config.yaml` file is excluded from version control by `.gitignore` — never commit it.

### Core settings

```yaml
core:
  my_node_id: "!your_node_id"       # Your bot node's ID (from the Meshtastic app)
  dedup_window: 10.0                 # Seconds to suppress duplicate messages
  database:
    db_path: "meshbot_data.db"       # Path for the SQLite node database
  channels:
    channel_0_name: "LongFast"       # Display names for each channel index (0–7)
    channel_1_name: "YourChannel1"
    # ...
```

### Meshtastic service

```yaml
services:
  meshtastic_service:
    node_ip: "127.0.0.1"            # IP address of your Meshtastic node
    node_port: 4403                  # TCP port (default: 4403)
    reconnect_base_delay: 5          # Seconds before first reconnect attempt
    reconnect_max_delay: 300         # Max seconds between reconnect attempts
```

### API keys

```yaml
services:
  aqicn_service:
    api_key: "your_api_key"
  github_service:
    api_key: "your_github_pat"       # GitHub personal access token
  positionstack_geocode_service:
    api_key: "your_positionstack_key"
    country_limit: "US"              # Optional: restrict geocoding to a country
```

### Modules

Each module can be enabled/disabled and configured to respond only to direct messages:

```yaml
modules:
  ping:
    enabled: true
    dm_only: true        # Only respond to direct messages
    interval_seconds: 0  # 0 = triggered by command only; >0 = also runs on a schedule
```

See `config.example.yaml` for the full list of module options.

## Bot Commands

Users interact with MeshBot by sending `!command` messages either as direct messages to the bot node or on a configured channel.

| Command | Description | Example |
|---------|-------------|---------|
| `!ping` | Test connectivity. Responds with signal info (SNR, hops). | `!ping` |
| `!about` | Show bot info and contact details. | `!about` |
| `!aqi <location>` | Current air quality for a location. | `!aqi Detroit` |
| `!help` | List available commands. | `!help` |
| `!weather <location>` | Current weather conditions for a location. | `!weather Detroit, MI` |
| `!forecast <location>` | 2-day weather forecast for a location. | `!forecast Ann Arbor` |
| `!alerts <location>` | Active NWS weather alerts for a location. | `!alerts Michigan` |
| `!nodesearch <query>` | Search the node database by name, ID, or proximity. | `!nodesearch John` / `!nodesearch near Ann Arbor, MI` |
| `!highnodes` | List the 5 nodes with the highest reported altitude. | `!highnodes` |
| `!stats [mode]` | Usage statistics. Modes: `commands`, `users`, `channels`. | `!stats users` |
| `!michmesh` | Show MichMesh community setup information. *(Michigan-specific — see below)* | `!michmesh` |

> **Note:** Commands that appear in `!help` are determined by enabled modules. If a module is disabled in `config.yaml`, its command will not respond.

> **`!michmesh`** is a community-specific command included as a working example of a simple info command. It responds with a hardcoded message pointing to [MichMesh](https://tinyurl.com/michmesh) setup documentation. If you're not part of that community, disable it in `config.yaml` or use it as a template to create your own regional or community info command.

## Background Modules

These modules run on a schedule and push messages to configured channels without requiring a user command.

| Module | Description | Default Interval |
|--------|-------------|-----------------|
| `local_aqi_alerts` | Polls the AQICN API for AQI alerts at a location and posts them to a channel. | Every 30 minutes |
| `local_nws_alerts` | Polls the NWS API for active alerts in a configured zone and posts them to a channel. | Every 30 minutes |
| `meshtastic_firmware_monitor` | Checks GitHub for new Meshtastic firmware releases and announces them. | Every 12 hours |
| `meshtastic_app_monitor` | Checks for new Meshtastic Android and iOS app releases and announces them. | Every 12 hours |

Configure the NWS zone in `config.yaml`:

```yaml
modules:
  local_nws_alerts:
    enabled: true
    interval_seconds: 1800
    zone: "MIZ075"      # Your NWS public zone ID (e.g. MIZ075 = Washtenaw County, MI)
    channels: [7]        # Channel indices to post alerts to
```

Find your NWS zone ID at [alerts.weather.gov](https://alerts.weather.gov/).

## Admin Dashboard

MeshBot runs an interactive terminal dashboard. Use the command input at the bottom to manage the bot at runtime.

| Command | Description |
|---------|-------------|
| `help` / `?` | Show available admin commands |
| `status` | Show enabled/disabled status of all modules |
| `toggle <module>` | Enable or disable a module by name |
| `reload` | Reload `config.yaml` and restart all modules and scheduled jobs |
| `nodesearch <query>` | Search the node database (name, ID, or `city, state`) |
| `rolesearch <role>` | Search nodes by their configured role |
| `directnodes` | List nodes with zero hops (directly connected) |
| `neighbornodes` | List recently heard non-MQTT nodes |
| `highnodes` | List nodes with the highest reported altitude |
| `stats` | Show bot and mesh statistics |
| `exit` | Shut down the bot |

## Project Structure

```
MeshBot/
├── commands/       # Command definitions (trigger words and event topics)
├── core/           # Core components: dispatcher, database, event bus, scheduler, plugin manager
├── interfaces/     # Abstract base classes for commands, modules, and services
├── models/         # Data models
├── modules/        # Command handlers and scheduled task implementations
├── services/       # External service integrations (Meshtastic, weather APIs, GitHub)
├── ui/             # Textual terminal dashboard
├── utils/          # Utility functions (geo, time)
├── main.py         # Entry point
├── config.example.yaml
└── requirements.txt
```

## Adding Custom Modules

MeshBot uses a plugin architecture. To add a new command:

1. Create a command file in `commands/` that extends `BotCommand` and defines a `trigger` and `event_topic`.
2. Create a module file in `modules/` that extends `BotModule`, subscribes to the event topic, and implements the logic.
3. Add the module configuration to `config.yaml` under `modules:`.

The plugin manager discovers and loads all modules automatically at startup and on `reload`.

See existing commands/modules for examples.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.
