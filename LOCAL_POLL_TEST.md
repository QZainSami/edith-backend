# Local polling test — prepared settings

The private backend .env and middleware include/edith_config.h now share a generated device token. Existing LM Studio and Wi-Fi values are preserved. The backend uses poll mode, firmware polling is enabled, and firmware local HTTP controls are disabled by default. Private backup files ending .pre-poll.bak preserve the previous settings. No firmware was uploaded and no backend process was restarted automatically.

## Run the test

1. Keep the PC and ESP32 on the same home network for this first test. The PC's current Ethernet address is 192.168.100.108. If that changes, update EDITH_SERVER_URL in the private firmware configuration. This is not the VirtualBox adapter address 192.168.56.1.
2. Stop the existing EDITH backend with Ctrl+C in its terminal. Keep LM Studio and Gemma running.
3. Open a terminal in EDITH Backend and run:

```powershell
uv run python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

4. In the PlatformIO project, Build and Upload the new configuration to the ESP32. The earlier successful build was before this private configuration was enabled; rebuild before upload. Keep the board powered.
5. Open http://127.0.0.1:8000 in your browser. Username: edith. Read EDITH_WEB_PASSWORD from your private .env for the generated password. Do not share or commit it. If the browser has cached different credentials, use a private browser window.
6. Click Refresh device status. Once the ESP32 has polled, online should be true.
7. Click sad or happy, wait about 3 seconds, then Refresh device status. Check mood matches desired_mood and applied is true. Command queued alone does not prove the face was displayed.
8. Test a chat message and confirm Reply: lmstudio, Detector: lmstudio and the matching physical face.

This temporary HTTP setup is for the trusted LAN only. Do not port-forward it. A Windows Firewall private-network rule may be needed; do not disable the firewall. If the ESP32 cannot reach the PC, check same network, PC address and inbound access to port 8000. Mobile hotspot testing comes after hosting; do not change the Wi-Fi credentials yet.

The ESP32's old local web page is disabled in polling mode, so use the backend's page. Wi-Fi loss should leave animations running; after reconnect, the latest unexpired face command should be delivered. The status can show offline during backoff.

## Restore previous local mode

Stop the backend, copy .env.pre-poll.bak over .env, copy include/edith_config.h.pre-poll.bak over include/edith_config.h, then rebuild/upload and restart the backend. These backups are private and ignored by Git.
