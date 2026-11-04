# ☁️ EDITH online: Render + Gemini + Neon

This setup runs the backend and AI without leaving your computer on:

```text
Android app + ESP32 → Render HTTPS backend → Gemini API
                                          → Neon PostgreSQL
```

Source stays in GitHub. Gemini replaces the local Gemma/LM Studio model for this deployment. The existing local setup continues to work when `LLM_PROVIDER=lmstudio` and `DATABASE_URL` is blank. Your existing private `.env` is not changed by these source updates.

## 1. Push the updated backend

Run inside your backend repository:

```text
git add .
git diff --cached --stat
git commit -m "Add Gemini and persistent PostgreSQL for Render hosting"
git push origin main
```

The Dockerfile and lockfile include the new storage dependency. Do not upload your private `.env`, filled-in cloud settings, database URL or API key.

## 2. Create a Gemini API key

Open [Google AI Studio API keys](https://aistudio.google.com/apikey), sign in and create a key for a **Free Tier** project. Keep billing disabled if you only want the free API quota. A Google AI Pro subscription is not required for this free tier.

The configured starting model is `gemini-3.1-flash-lite`, listed with free input/output usage in the [current pricing documentation](https://ai.google.dev/gemini-api/docs/pricing). Availability and quotas depend on your account/model/region and can change. Check the project’s actual tier and limits in AI Studio. Free-tier data may be used to improve Google's products; see its terms before sending private conversations.

Copy the key privately into Render, never into chat, source or screenshots. The backend uses the [Gemini OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai) through its existing HTTP client, with structured reply/mood/reason validation. Quota errors, network errors and invalid model output produce labeled rules fallback replies; there is no automatic switch to a paid project or a different model.

## 3. Create a Neon PostgreSQL database

1. Open [Neon](https://console.neon.tech/), create an account and choose the **Free** plan.
2. Create a project such as `edith`. Choose a database region near the Render service, ideally the same city if offered.
3. Open **Connect**. Choose a **pooled connection string** if offered.
4. Copy only the complete URL beginning `postgresql://`, including its password and TLS query parameters. Do not copy a surrounding `psql` command or quotation marks.

Render's free web-service filesystem is temporary; our old SQLite file would be lost on restart/redeploy. `DATABASE_URL` stores the mailbox, preferences, timers, stopwatch and alarms in PostgreSQL instead. On first launch this backend creates its own `state` and `companion` tables in the configured database. Use a dedicated database for EDITH. Local SQLite data is not automatically copied: the hosted deployment begins with fresh settings, so set your city/time zone again.

Neon's [Free plan](https://neon.com/pricing) currently has 100 CU-hours/month and 1 GB storage per project, and can sleep when idle. Frequent app/device polling keeps the database active and consumes compute; this is not unlimited 24/7 hosting. Monitor usage. Do not select a paid plan merely to bypass a quota without reviewing the cost.

## 4. Complete the Render form

Choose **Web Service**, connect `QZainSami/edith-backend`, and use:

| Setting | Value |
| --- | --- |
| Runtime | Docker |
| Branch | `main` |
| Root Directory | Blank |
| Instance | Free |
| Health Check Path (Advanced) | `/healthz` |

Set these **Environment Variables**:

| Key | Value |
| --- | --- |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `GEMINI_API_KEY` | Your private AI Studio key |
| `DEVICE_TRANSPORT` | `poll` |
| `EDITH_DEVICE_TOKEN` | The same private 32+ character token used by your ESP32 |
| `EDITH_WEB_USER` | Your existing web username |
| `EDITH_WEB_PASSWORD` | Your existing private web password, at least 16 characters |
| `DATABASE_URL` | The full private Neon connection URL |

Keep the existing device token when reusing firmware; generating a different token on only one side prevents the ESP32 from connecting. Leave `PORT` to Render. You do not need `EDITH_IP`, `EDITH_STATE_DB` or `LMSTUDIO_URL` in this hosted configuration. `render.env.example` contains only placeholders for reference; add real values directly in Render's secret settings.

After the code is pushed and all values are entered, click **Deploy web service**. Use exactly one instance/worker; the Docker command already sets one worker and reads Render's `PORT`.

The app fails startup on Render if persistent PostgreSQL or polling mode is missing, rather than silently storing timers in a temporary file. Database errors return a sanitized HTTP 503 without exposing the connection string. Health checks do not generate Gemini responses or spend model tokens.

## 5. Connect and verify

1. Wait for Render to show **Live**. Copy its exact HTTPS service URL.
2. Open it in a browser and sign in with the configured web username/password. Use **Check Gemini** and send a short test message. A model check confirms the model is listed, not that a full inference succeeds.
3. In EDITH Android Settings, use that HTTPS URL and the same web login. Existing app API routes remain compatible, even if an older app button is still labeled “Check LM Studio.” Model responses are labeled `gemini`.
4. The ESP32 must use that same HTTPS backend URL, its matching bearer token and the correct TLS root CA, with HTTP test mode disabled. Updating the app URL does not update ESP32 firmware. Until the firmware URL is changed and uploaded, backend/model may be online while ESP32 remains offline. Never disable certificate validation as a workaround.
5. Set weather city/time zone again. Start and pause a stopwatch, then manually restart the Render service and confirm the elapsed value remains. This checks the real persistent database. Test face delivery and timers after the ESP32 reconnects.

The stable Render URL replaces the changing Quick Tunnel address. Your computer can then be off; Render, Neon and Gemini still need to be available and within their quotas.

## Free-tier limits and troubleshooting

- Render Free sleeps after 15 minutes without inbound traffic; waking can take about a minute. The phone may time out during a cold start: open the service in a browser, wait for it to wake, then reconnect. Outbound bandwidth/build allowances also apply. See [Render's limits](https://render.com/docs/free).
- A powered, polling ESP32 or an open Android app generates frequent requests. This can prevent idle sleep, but also uses hosting/database quotas. Free plans are suitable for demos and limited use, not an uptime guarantee.
- Render's own free PostgreSQL offer expires after 30 days; this guide uses a separate Neon database instead.
- If deployment cannot install dependencies, confirm the pushed commit includes `pyproject.toml`, `uv.lock`, `storage.py` and the updated Dockerfile.
- If database setup fails, re-copy the complete Neon URL without shell wrappers, check its password/TLS parameters and database usage. Do not post the URL or raw logs containing credentials publicly.
- If Gemini returns 401/403, check the key/project/model access. A 429 means rate limit or quota; the backend falls back to rules. AI Studio quotas and model metadata are not a guarantee of unlimited free generation.
- The startup tables/queries have offline contract tests. Real Gemini requests and PostgreSQL connectivity require your own credentials and must be verified after configuration; automated tests make no paid API calls.
