# Create and configure Pro Response for Slackbot

Pro Response runs in **Socket Mode** by default, so you don't need a public URL
or ngrok — it opens an outbound WebSocket to Slack. The fastest path is to
create the app from the manifest below.

## 1. Create the app from a manifest

1. Go to <https://api.slack.com/apps> → **Create New App** → **From an app
   manifest**.
2. Pick your workspace, choose **YAML**, and paste this manifest:

```yaml
display_information:
  name: Pro Response for Slackbot
  description: An AI writing assistant that polishes your messages.
features:
  bot_user:
    display_name: Pro Response
    always_online: true
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: false
  slash_commands:
    - command: /pro
      description: Rewrite a message and preview it before posting
      usage_hint: "[tone] your message"
      should_escape: false
    - command: /pr
      description: Rewrite a message (alias of /pro)
      usage_hint: "[tone] your message"
      should_escape: false
    - command: /prr
      description: Get a private rewrite recommendation
      usage_hint: "[tone] your message"
      should_escape: false
  shortcuts:
    - name: "Pro Response: rewrite"
      type: message
      callback_id: proresponse_rewrite
      description: Refine this message with Pro Response
    - name: Compose with Pro Response
      type: global
      callback_id: proresponse_compose
      description: Draft and refine a new message
oauth_config:
  scopes:
    bot:
      - commands
      - chat:write
      - chat:write.public
settings:
  event_subscriptions:
    bot_events:
      - app_home_opened
  interactivity:
    is_enabled: true
  socket_mode_enabled: true
  org_deploy_enabled: false
  token_rotation_enabled: false
```

3. Review and **Create**.

## 2. Get your tokens

- **App-level token (Socket Mode):** *Basic Information* → *App-Level Tokens* →
  **Generate Token and Scopes**. Add the `connections:write` scope. Copy the
  `xapp-…` value → this is `SLACK_APP_TOKEN`.
- **Bot token:** *OAuth & Permissions* → **Install to Workspace** → copy the
  **Bot User OAuth Token** (`xoxb-…`) → this is `SLACK_BOT_TOKEN`.
- **Signing secret** (only needed for HTTP mode): *Basic Information* → *App
  Credentials* → `SLACK_SIGNING_SECRET`.

## 3. Configure and run

```bash
cp .env.example .env
# Fill in SLACK_BOT_TOKEN, SLACK_APP_TOKEN, and OPENAI_API_KEY (or ANTHROPIC_API_KEY)
pip install -e ".[anthropic]"
proresponse-slack
```

You should see `Starting Pro Response in Socket Mode`. Type `/pro hello there`
in any channel to test.

## 4. (Optional) HTTP mode instead of Socket Mode

If you'd rather run behind a public HTTPS endpoint:

1. Set `SLACK_MODE=http` and `SLACK_SIGNING_SECRET=…` in `.env`.
2. In the manifest/app settings, disable Socket Mode and set request URLs to
   `https://your-host/slack/events` for **Interactivity**, **Slash Commands**,
   and **Event Subscriptions**.
3. Run `proresponse-slack` (it binds `SERVICE_IP:SERVICE_PORT`, default
   `0.0.0.0:3000`).

## Scopes explained

| Scope | Why |
| --- | --- |
| `commands` | Register the `/pro`, `/pr`, `/prr` slash commands. |
| `chat:write` | Post the rewrite to a channel and send ephemeral previews. |
| `chat:write.public` | Post to public channels the bot hasn't been added to. |

The App Home tab uses the `app_home_opened` bot event (already in the manifest).
