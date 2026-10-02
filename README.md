@@ -0,0 +1,110 @@
# Ooma Integration for Home Assistant

[![HACS Custom Integration](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.8+-blue.svg)](https://home-assistant.io)

Custom Home Assistant integration for **Ooma (Telo / Linx / Cloud Account)**. Enables real-time call tracking, missed call monitors, voicemail status indicators, and event-driven smart home automations (TTS announcements, notifications, smart lights).

---

## Features

- **Sensors:**
  - `sensor.ooma_last_caller`: Displays the latest caller's name or number with rich attributes (duration, timestamp, type, call history).
  - `sensor.ooma_voicemails`: Tracks unread and total voicemail messages.
  - `sensor.ooma_missed_calls`: Count and history of recent missed calls.
  - `sensor.ooma_status`: Cloud/account connection status (`connected` / `disconnected`).
- **Events:**
  - `ooma_incoming_call`: Fired when a new incoming call is detected.
  - `ooma_missed_call`: Fired when a missed call is detected.
  - `ooma_voicemail_received`: Fired when a new voicemail is left.
- **Easy UI Setup:** Native Config Flow with username/phone & password validation and configurable polling interval.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right corner and choose **Custom repositories**.
3. Paste the URL of this repository, select Category **Integration**, and click **Add**.
4. Search for **Ooma**, click **Download**, and restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/ooma` directory into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for **Ooma**.
3. Enter your **Ooma Phone Number / Username** and **Password** (the credentials you use to log into [my.ooma.com](https://my.ooma.com)).
4. Click **Submit**.

---

## Example Automations

### 1. Alexa / Google Speaker Call Announcement

Announce the caller name over your smart speakers when a call arrives:

```yaml
alias: "Ooma - Announce Incoming Call"
description: "Speaks the caller name over media player"
trigger:
  - platform: event
    event_type: ooma_incoming_call
action:
  - service: tts.speak
    target:
      entity_id: tts.piper
    data:
      media_player_entity_id: media_player.living_room_speaker
      message: "Incoming call from {{ trigger.event.data.caller_name }}"
mode: queued
```

### 2. Mobile Notification for Missed Calls

```yaml
alias: "Ooma - Missed Call Notification"
trigger:
  - platform: event
    event_type: ooma_missed_call
action:
  - service: notify.notify
    data:
      title: "Missed Call"
      message: "You missed a call from {{ trigger.event.data.caller_name }} ({{ trigger.event.data.caller_number }}) at {{ trigger.event.data.timestamp }}."
```

### 3. Flash Living Room Lights on New Voicemail

```yaml
alias: "Ooma - Voicemail Light Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.ooma_voicemails
    above: 0
action:
  - service: light.turn_on
    target:
      entity_id: light.living_room
    data:
      flash: short
```

---