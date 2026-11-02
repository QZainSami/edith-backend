# Milestone 5: hosted device connection

## What was implemented

Local mode is unchanged by default. Your existing .env was not modified. The firmware's EDITH_CLOUD_ENABLED remains 0, so the working local web controls, pins, faces and animations remain available if you build/upload it later. No firmware has been flashed by this update.

New poll mode lets the ESP32 initiate authenticated requests to the backend through a hotspot. A one-slot mailbox keeps the latest requested face (intermediate thinking faces may be skipped if generation finishes before a poll). Commands have random IDs, are re-delivered until acknowledged, and expire after 120 seconds (30 seconds for thinking). The firmware reports acknowledgement after the animation finishes. The backend exposes last reported mood, online state and pending/applied state; a queued command is not an acknowledgement.

A separate FreeRTOS task handles network requests. Only the animation loop uses the OLED. Polling runs about every 1.5 seconds when healthy, backing off up to 30 seconds on failure. HTTP timeouts and the TLS handshake can extend failure recovery time. Wi-Fi reconnect remains enabled. NTP time and the correct root CA are required for certificate verification. There is no setInsecure bypass. A firmware reboot reports a fresh acknowledgement; an expired command is not replayed. The face stays at its last expression if networking fails.

## Local verification before hosting

The full backend tests can be run from this folder with `uv run python -m pytest -q`. They use mock device/model responses, not the live OLED. Tests cover authentication, rules, model fallback, queue delivery, acknowledgements, expiry and state recreation.

Compile the PlatformIO project before uploading using its Build button or `pio run`. During the agent's check, the installed Xtensa compiler could not launch on Windows: Illegal System DLL Relocation. Consequently this firmware change has not yet passed a build check. If Build works in your own VS Code session, we can proceed with the LAN polling test; otherwise resolve the toolchain environment first. No dependency was added to the firmware.

For a LAN-only poll test:

1. Keep a backup of .env. Generate separate random device and web secrets (for example `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"` twice). Do not paste secrets into a public repo or chat.
2. Set DEVICE_TRANSPORT=poll, EDITH_DEVICE_TOKEN to the first secret, EDITH_WEB_USER=edith, and EDITH_WEB_PASSWORD to the second secret. Device token must be at least 32 characters; web password at least 16.
3. Run `uv run python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1` on the PC, on a trusted LAN only. Allow access on the private network if Windows asks. HTTP is for this test only.
4. In the PlatformIO project's private include/edith_config.h, set EDITH_CLOUD_ENABLED=1, EDITH_ALLOW_HTTP_TEST=1, EDITH_SERVER_URL to http://YOUR-PC-LAN-IP:8000, and EDITH_DEVICE_TOKEN to the same device secret. Existing Wi-Fi credentials were preserved in that private file. Change to your hotspot credentials if needed.
5. Build, then upload only when ready. The local ESP web server is disabled in cloud mode by default to avoid an unauthenticated alternate control path.
6. Open the backend in a browser, enter the web credentials, click a mood, and Refresh device status after a few seconds. Verify desired_mood, mood, online and applied. Both PC and ESP must be on the same reachable network for this LAN test.
7. Restore DEVICE_TRANSPORT=local and EDITH_CLOUD_ENABLED=0 for the previous workflow. Rebuild/upload if switching firmware modes.

No real credentials were generated for you and no modes were activated automatically.

## Hosting preparation

Dockerfile, .dockerignore and render.yaml are provided for a single-instance Render deployment. Dependencies use the existing uv.lock. The container runs as a non-root user. The public health check exposes only ok=true; the UI, API docs and browser API require HTTP Basic credentials in poll mode. Device requests require a different bearer token. Use HTTPS for real hosting. This is single-owner prototype authentication, not a multi-user app or production abuse-protection system.

Render's Blueprint can generate device and web secrets; obtain them privately from the service environment panel after setup. Configure the model URL, exact model ID, and model authentication token. Do not use 127.0.0.1 for the model URL on Render: it would refer to the cloud container, not your PC.

Your home PC still needs to stay awake with Gemma serving. A secure, authenticated model connection from the cloud to that PC is a separate remaining step. Require LM Studio authentication, disable unneeded per-request MCPs, and don't forward port 1234 publicly. A suitable authenticated tunnel/relay must be configured and tested before model requests will work remotely. No tunnel has been installed or exposed by this update.

After the actual backend hostname exists, install the correct trusted root CA PEM in EDITH_ROOT_CA, set EDITH_SERVER_URL to the https:// origin, set EDITH_ALLOW_HTTP_TEST=0, and use the deployment's device token. Supply hotspot credentials. Never put the browser password or LM Studio token in firmware. Do not flash an unverified/incomplete cloud configuration.

Render free hosting may sleep or restart, with cold-start delays and monthly usage limits. Its disk is ephemeral: SQLite state may be lost on redeploy/restart, even though it survives application process recreation on a persistent filesystem. Command IDs prevent old acknowledgements matching new commands, and short expiries avoid replay after long outages. After a reset you may need to send the desired face again. This project uses one backend instance/worker; a multi-instance deployment requires shared storage.

## Still to finish before the university test

- Resolve/verify the firmware build and run the local polling test.
- Set up the hosting account/source repo and review exactly what will be uploaded. Keep .env, include/edith_config.h and backups private.
- Establish and authenticate the secure home-model connection.
- Deploy the backend, configure its URL/token/root CA in firmware and test HTTPS.
- Test with ESP32 on hotspot, phone on mobile internet, and the home PC on its separate home network. Test disconnect/reconnect, expired commands, invalid credentials, and cold starts.

## References
- Render Blueprint: https://render.com/docs/blueprint-spec
- Render free limits: https://render.com/docs/free
- uv Docker workflow: https://docs.astral.sh/uv/guides/integration/docker/
- Firmware inspiration, not copied code: https://github.com/SathiyaSenpai/deskbot
