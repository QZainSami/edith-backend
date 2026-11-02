# EDITH roadmap

## Working now
- ESP32-S3 + SH1106 OLED, smooth transitions, blinking and eight expressions.
- Typed web chat; Gemma 4 E2B through LM Studio on the home PC.
- Contextual face suggestions with validated structured output and rules fallback.

## Milestone 5: portability
- Hosted backend and chat page; ESP32 connects outward over the mobile hotspot.
- Home PC continues serving Gemma: PC must remain on, awake and online.
- Keep local HTTP mode for development.
- Add authenticated HTTPS polling, explicit acknowledgement, stale-command expiry and reconnect backoff.
- Add browser authentication, deploy preparation, then a secure model connection.
- Account setup, public hosting and real hotspot tests remain to be completed.

## Future hardware and app (requested by user)
- Companion app, including phone-based voice input/output options.
- Touch sensor: shy/uwu response to gentle interaction; angry reaction to repeated touches, with debounce and cooldown.
- Sound cues and eventually spoken replies from suitable audio hardware.
- Wake word "EDITH": local wake detection, then record speech, speech-to-text, LLM response, text-to-speech, speaker playback.
- Animate mouth in sync with spoken audio; stop/cancel listening and speaking.
- Wake-word detection itself requires ongoing microphone input; after detection, start the conversation recording. The LLM text endpoint does not itself transcribe audio.
- Select mic, speaker amplifier, speaker and touch input before wiring; verify voltage and current requirements. A buzzer provides tones, not speech.
- Reference for ideas: https://github.com/SathiyaSenpai/deskbot
- Do not add relay control or hardware actions as LLM tools without an explicit feature decision.
