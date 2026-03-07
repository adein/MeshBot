# Contributing to MeshBot

Thank you for your interest in contributing! This document covers how to set up a development environment, the project's plugin architecture, and how to submit changes.

## Development Setup

```bash
git clone https://github.com/adein/MeshBot.git
cd MeshBot
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml with your node's IP and API keys
```

Python 3.10 or later is required.

## How to Add a Command

Commands are split across two layers: a **command** (defines the trigger word) and a **module** (handles the logic).

### 1. Create the command file

Add a file to `commands/` that extends `BotCommand`:

```python
# commands/mycommand_cmd.py
from interfaces.bot_command import BotCommand

class MyCommand(BotCommand):
    """
    Brief description of what this command does.
    """
    trigger = "mycommand"
    event_topic = "bot.command.mycommand"
```

The `trigger` is the word users type after `!` (e.g., `!mycommand`). The `event_topic` is the internal event bus topic the command publishes to.

### 2. Create the module file

Add a file to `modules/` that extends `BotModule` and subscribes to the event topic:

```python
# modules/mycommand.py
from interfaces.bot_module import BotModule
from models.command import CommandData

class MyCommand(BotModule):
    """
    Module to respond to 'mycommand' commands.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        if self.event_bus:
            self.event_bus.subscribe("bot.command.mycommand", self._handle_command)

    def execute(self):
        # Called on schedule. Leave empty if command-only.
        pass

    def _handle_command(self, data: CommandData):
        if not self.is_enabled():
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            return
        if self.is_dm_only() and not data.is_dm:
            return
        # data.parameters contains arguments passed after the command
        self.mesh_service.send_reply("Hello from MyCommand!", data)
```

### 3. Add configuration

Add the module to `config.yaml` under `modules:`:

```yaml
modules:
  mycommand:
    enabled: true
    dm_only: false
    interval_seconds: 0
```

The module name in `config.yaml` must match the filename (without `.py`) in `modules/`.

### 4. Update config.example.yaml

Add the same block to `config.example.yaml` with appropriate placeholder values so other users know the option exists.

## How to Add a Scheduled Module

If your module should run on a timer (not just in response to commands), implement logic in `execute()` and set `interval_seconds` to a non-zero value in the config. The scheduler calls `execute()` on the configured interval.

## How to Add a Service

Services wrap external APIs. Add a file to `services/` that extends `BotService`. Read configuration via the `config` dict passed to the constructor. Access your service from a module via `global_services` or by instantiating it directly.

## Submitting Changes

1. Fork the repository and create a branch from `develop`.
2. Make your changes. Keep commits focused and atomic.
3. Test manually against a real Meshtastic node or use the admin dashboard to verify your module loads.
4. Open a pull request against `develop` with a clear description of what the change does and why.

## Code Style

- Follow existing patterns in the codebase.
- Use type hints where they add clarity.
- Keep module logic self-contained — avoid tight coupling between modules.
- Do not commit `config.yaml`, log files, or database files. These are excluded by `.gitignore`.
