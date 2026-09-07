# hermes-song-plugin

A restricted Hermes Agent plugin that exposes exactly one tool, `generate_song`,
which shells out to a local HeartMuLa install to generate a song from
lyrics + tags. No other tool access is exposed by this plugin.

## Install on the GPU machine

```bash
git clone https://github.com/mcbuehler/hermes-song-plugin.git
mkdir -p ~/.hermes/plugins
cp -r hermes-song-plugin/plugins/song-generator ~/.hermes/plugins/song-generator
```

Then edit the path constants at the top of
`~/.hermes/plugins/song-generator/__init__.py` (or set the matching
`HEARTMULA_*` environment variables) to point at your actual heartlib
clone, venv, and checkpoint directory.

## Enable the plugin and restrict the Telegram channel

```bash
hermes config set plugins.enabled '["song-generator"]'
hermes config set platform_toolsets.telegram '["clarify", "song_generator"]'
hermes gateway restart   # or: hermes gateway start
```

## Environment variables (optional overrides)

| Variable | Default |
|---|---|
| `HEARTMULA_HEARTLIB_DIR` | `/home/youruser/heartlib` |
| `HEARTMULA_VENV_PYTHON` | `$HEARTLIB_DIR/.venv/bin/python` |
| `HEARTMULA_MODEL_PATH` | `$HEARTLIB_DIR/ckpt` |
| `HEARTMULA_MODEL_VERSION` | `3B` |
| `HEARTMULA_OUTPUT_DIR` | `$HEARTLIB_DIR/assets/generated` |
| `HEARTMULA_MAX_AUDIO_MS` | `240000` (4 min) |
| `HEARTMULA_GEN_TIMEOUT_S` | `900` (15 min) |
| `HEARTMULA_LAZY_LOAD` | `true` |
