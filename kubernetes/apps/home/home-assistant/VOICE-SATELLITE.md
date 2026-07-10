# Home Assistant voice satellite setup

## Goal

Use a Seeed ReSpeaker Lite (XIAO ESP32-S3 + XMOS XU316) as a wake-word
satellite that:

- Listens via the on-board 2-mic array (hardware noise suppression, AEC).
- Runs wake words locally on the ESP32-S3 via ESPHome `micro_wake_word`.
- Routes TTS responses to a Sonos speaker in the same room instead of the
  satellite's onboard amp.
- Uses Home Assistant's Assist pipeline with Wyoming Whisper (STT) and
  Wyoming Piper (TTS) running on the same HA instance.

## Components

```
kubernetes/apps/home/
├── esphome/app/
│   ├── config/
│   │   └── common/
│   │       └── respeaker-satellite-base.yaml  # FormatBCE base, MP3 tweak (git)
│   ├── helm-release.yaml                       # mounts common-packages ConfigMap
│   └── kustomization.yaml                       # generates the ConfigMap
└── home-assistant/app/
    └── config/
        └── automations.yaml                    # Sonos TTS redirect (reference)
```

**Device YAMLs are managed in the ESPHome UI**, not in git. They live on
the ESPHome PVC at `/config/<device>.yaml` and reference the git-managed
base via `!include common/respeaker-satellite-base.yaml`.

## Architecture

```
[Voice] -> ReSpeaker Lite (ESP32-S3, micro_wake_word)
                |
                | HA voice_assistant API (websocket)
                v
        Home Assistant (Assist pipeline)
                |
                | Wyoming protocol
                v
        Whisper (STT) -> LiteLLM/OpenAI -> Piper (TTS)
                                              |
                                              | generates .mp3 file
                                              v
                                HA emits esphome.tts_uri event
                                              |
                                              v
                  HA automation -> media_player.play_media (announce=true)
                                              |
                                              v
                                       Sonos (with ducking)
```

## Why MP3 instead of FLAC

Sonos's `announce: true` feature uses the AudioClip API, which silently
rejects FLAC files (no error, no playback). Regular `play_media` accepts
FLAC because it goes through Sonos's full media pipeline.

HA's TTS layer defaults to MP3, but the ESPHome satellite entity overrides
this by reading the device's advertised `supported_formats` list and
picking the first entry tagged `purpose: announcement`. The default
FormatBCE config advertises FLAC, so HA asks Piper for FLAC.

The fix in `common/respeaker-satellite-base.yaml` advertises MP3 first:

```yaml
media_player:
  - platform: speaker_source
    id: external_media_player
    supported_formats:
      - format: mp3                  # <-- first match wins
        sample_rate: 22050
        num_channels: 1
        sample_bytes: 2
        purpose: announcement
      - format: flac                 # fallback
        ...
```

After flashing a device with this base, the `esphome.tts_uri` event's URL
ends in `.mp3` instead of `.flac`, and Sonos's `announce: true` works
correctly.

## First-time setup

### 1. Create the device YAML in ESPHome UI

Open the ESPHome dashboard, click **NEW DEVICE**, give it a name
(e.g., `respeaker-kitchen`), skip the wizard, and paste:

```yaml
packages:
  respeaker-satellite: !include common/respeaker-satellite-base.yaml

esphome:
  name: respeaker-kitchen
  friendly_name: "ReSpeaker Kitchen"
  name_add_mac_suffix: false

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: "respeaker-kitchen-fallback"
    password: !secret wifi_password

ota:
  - platform: esphome
    password: !secret ota_password
```

Secrets come from `/config/secrets.yaml` on the PVC. The git-managed
base YAML is mounted read-only at `/config/common/respeaker-satellite-base.yaml`.

### 2. Flash via USB (one-time)

- Plug USB into the **XIAO ESP32-S3 module's port**, not the main ReSpeaker
  board port.
- If WebSerial hangs at "Running stub...", hold **BOOT**, press **RESET**,
  release **BOOT** to enter download mode. (The buttons are tiny tactile
  switches on the XIAO module itself, not the USR/MUTE buttons on the
  ReSpeaker board.)

After the first flash, OTA works over WiFi.

### 3. First boot auto-flashes the XMOS chip

The FormatBCE base YAML ships with the DFU image and applies it on first
run. LED flashes yellow during the update, green when done (~30s).
Don't power off during this.

### 4. Adopt in Home Assistant

Settings -> Devices & Services -> ESPHome -> **CONFIGURE** on the new
`respeaker-kitchen` entry. Paste the API encryption key when prompted.

### 5. Mute the onboard speaker

Find `switch.respeaker_kitchen_speaker_mute` and turn it **ON**. Persists
across reboots. This silences the satellite's onboard amp while still
emitting the `esphome.tts_uri` event for Sonos.

### 6. Set the Assist pipeline

On the satellite's device page in HA, set the Assist pipeline to use your
Wyoming Whisper (STT) and Wyoming Piper (TTS).

### 7. Deploy the Sonos TTS redirect automation

See `home-assistant/app/config/automations.yaml` for the YAML and
deployment options (paste into HA UI vs ConfigMap mount).

## Verifying

After setup, say "okay nabu, what time is it".

Expected sequence:
1. LED pulses purple (wake word detected, listening).
2. ~1-2 second pause (STT + LLM + TTS).
3. Response plays on the Sonos in the same room.
4. If Sonos was playing music, it ducks, plays TTS, then resumes.
5. LED returns to idle.

Check `Developer Tools -> Events -> Listen` for `esphome.tts_uri` to
confirm the URL ends in `.mp3`. If it ends in `.flac`, the
`supported_formats` change didn't take effect (reflash the device).

## Adding more satellites

1. In the ESPHome UI, create a new device with the same shape as the
   kitchen YAML but with a different `name`/`friendly_name`.
2. Add a new entry in `home-assistant/app/config/automations.yaml` with
   the new `device_id` and Sonos entity.

## Updating the FormatBCE base

This is a local fork. To pull upstream changes:

```bash
# From the repo root
curl -o kubernetes/apps/home/esphome/app/config/common/respeaker-satellite-base.yaml \
  https://raw.githubusercontent.com/formatBCE/Respeaker-Lite-ESPHome-integration/main/config/common/respeaker-satellite-base.yaml

# Then re-apply the supported_formats edit:
#   1. Find the media_player > external_media_player block.
#   2. Add the supported_formats list with MP3 first.
#   3. Diff and commit.
```

Check FormatBCE's changelog before updating — they may break things.
Test on a non-production satellite first if you have one.

## References

- FormatBCE repo: https://github.com/formatBCE/Respeaker-Lite-ESPHome-integration
- Seeed ReSpeaker Lite wiki: https://wiki.seeedstudio.com/xiao_respeaker/
- HA Sonos announce docs: https://www.home-assistant.io/integrations/sonos/#playing-media
- HA TTS preferred_format docs: https://www.home-assistant.io/integrations/tts/#preferred-audio-settings
