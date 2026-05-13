# Local testing guide

This guide explains how to run and test the Telegram IELTS Speaking bot locally, including how to get Telegram chat IDs manually **without using helper bots**.

---

## 1. What you need before starting

### Required accounts and tools

- A Telegram bot token from `@BotFather`.
- An OpenAI API key with access to:
  - Whisper transcription (`whisper-1`)
  - Chat Completions model used by the project (`gpt-4o`)
- Python 3.11 or 3.12.
- FFmpeg installed and available in your terminal.
- At least one Telegram group where you can add your bot.
- Ideally two Telegram user accounts for role testing:
  - one regular group member = student
  - one group admin/creator = teacher

### Check system dependencies

From the repository root:

```bash
python --version
ffmpeg -version
```

Expected:

- Python is `3.11.x` or `3.12.x`.
- `ffmpeg -version` prints FFmpeg version information.

---

## 2. Install and configure locally

### 2.1 Create a virtual environment

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2.2 Create `.env`

Copy the example file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
copy .env.example .env
```

Use a local folder for saved audio files:

```env
BOT_TOKEN=123456789:your_telegram_bot_token
OPENAI_API_KEY=sk-your_openai_api_key
VIDEO_SAVING_PATH=savings

# Use GROUP_ID for one group, or GROUP_IDS for several groups.
# ALLOWED_GROUP_IDS is also accepted as an optional alias.
GROUP_ID=-1001234567890
GROUP_IDS=-1001234567890,-1002345678901,-1003456789012
# ALLOWED_GROUP_IDS=-1001234567890,-1002345678901,-1003456789012
```

Notes:

- `GROUP_ID` is kept for backward compatibility.
- `GROUP_IDS` is comma-separated and is the preferred option for multiple groups.
- `ALLOWED_GROUP_IDS` is accepted as an optional alias for deployments that already use that name.
- If several variables are set, the bot combines all IDs and removes duplicates.
- On startup, the bot logs the loaded group ID values and the effective group list, but never logs `BOT_TOKEN` or `OPENAI_API_KEY`.
- `VIDEO_SAVING_PATH=savings` is safe for local testing; the app creates the folder automatically.

---

## 3. Get Telegram chat IDs manually, without other bots

You do **not** need `@userinfobot` or any other helper bot. Use Telegram Bot API updates from your own bot.

### Important rules

- Stop any currently running copy of the bot before using `getUpdates`.
- If the bot has a webhook configured, remove it first.
- Add your bot to the target group.
- Send a fresh message in that group after adding the bot.
- Group/supergroup IDs are usually negative numbers. Supergroups usually look like `-100...`.

### 3.1 Remove webhook if needed

Replace `<BOT_TOKEN>` with your real token:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
```

Expected response:

```json
{"ok":true,"result":true,"description":"Webhook was deleted"}
```

It is also fine if Telegram says no webhook existed.

### 3.2 Get your private chat ID

1. Open a private chat with your bot in Telegram.
2. Send `/start` or any text message.
3. Run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates"
```

Look for:

```json
"chat":{"id":123456789,"first_name":"...","type":"private"}
```

The `id` value is your private chat ID.

### 3.3 Get a group chat ID

1. Create or open your Telegram group.
2. Add your bot to the group.
3. Send a normal message in the group, for example:

```text
hello bot
```

4. Run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates"
```

Look for an update where the chat type is `group` or `supergroup`:

```json
"chat":{"id":-1001234567890,"title":"IELTS Test Group","type":"supergroup"}
```

Use the `chat.id` value as `GROUP_ID` or inside `GROUP_IDS`.

### 3.4 If `getUpdates` returns an empty result

If you see:

```json
{"ok":true,"result":[]}
```

try these fixes:

1. Make sure your local bot process is stopped.
2. Run `deleteWebhook` again with `drop_pending_updates=true`.
3. Send a **new** message in the group after deleting the webhook.
4. If the group is private and the bot does not see normal messages, send a command in the group:

```text
/start@YourBotUsername
```

5. If you still do not receive group updates, temporarily disable BotFather privacy mode:
   - Open `@BotFather`.
   - Send `/setprivacy`.
   - Choose your bot.
   - Select `Disable`.
   - Send another new message in the group.
   - Run `getUpdates` again.

You can enable privacy again after collecting the chat ID if you want.

### 3.5 Get several group IDs

Repeat the group steps for every group and collect IDs:

```env
GROUP_IDS=-1001111111111,-1002222222222,-1003333333333
```

Do not add spaces unless you know what you are doing. The parser trims spaces, but keeping the value compact is easier to read.

### 3.6 Clear old updates after collecting IDs

After you have the IDs, clear pending updates so local testing starts cleanly:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
```

Then start the local bot.

---

## 4. Run the bot locally

From the repository root, with the virtual environment activated:

```bash
python -m bot.bot
```

Expected terminal behavior:

- The process keeps running.
- Logs appear in the terminal.
- Startup logs include a line like `Group access config loaded: ... effective_group_ids=[...]`.
- This log should show your `GROUP_IDS` values. It must not show `BOT_TOKEN` or `OPENAI_API_KEY`.
- Press `Ctrl+C` to stop it.

If Telegram reports that another `getUpdates` request is running, stop all other bot processes and wait a few seconds, then run again.

---

## 5. Test access control and roles

The bot checks membership in the configured allowed groups.

### 5.1 Outsider: no access

Use a Telegram account that is **not** in any allowed group.

1. Open private chat with the bot.
2. Send `/start`.

Expected:

```text
Доступ закрыт.
Ты должен состоять в группе, которую обслуживает этот бот.
```

### 5.2 Student role

Use an account that is a regular member of at least one allowed group.

1. Make sure the account is not an admin/creator in any allowed group.
2. Send `/start` to the bot in private chat.

Expected:

- The bot asks the student to choose language.
- The student should **not** see the teacher panel.

### 5.3 Teacher role

Use an account that is admin or creator in at least one allowed group.

1. Make the account an admin in one allowed group.
2. Send `/start` to the bot in private chat.

Expected:

- The existing teacher panel appears.
- The teacher can send one or more student voice recordings.
- Teacher detail buttons still work.

### 5.4 Multi-group priority check

If a user is:

- regular member in Group A
- admin in Group B

and both groups are in `GROUP_IDS`, the user should be treated as `teacher` because admin/creator in **any** allowed group has priority.

---

## 6. Test the new student IELTS Speaking flow

Use a regular group member account.

### 6.1 Happy path: Russian feedback

1. Send `/start` in private chat.
2. Choose `🇷🇺 Русский`.
3. Choose `Part 1`, `Part 2`, or `Part 3`.
4. Wait for the generated IELTS Speaking question.
5. Record a voice answer in English.
6. Send the voice message.

Expected:

- The bot says it received the voice and is transcribing.
- Whisper transcribes the answer.
- GPT evaluates the answer using:
  - selected IELTS part
  - generated question
  - student transcript
  - selected language
- Feedback is returned in Russian.
- Feedback includes estimated band, fluency/coherence, lexical resource, grammar, pronunciation notes, improved version, and practical advice.

### 6.2 Happy path: Uzbek feedback

1. Send `/start`.
2. Choose `🇺🇿 O‘zbek`.
3. Choose any part.
4. Answer the generated question by voice in English.

Expected:

- Student-facing messages after language selection are in Uzbek.
- Feedback is in Uzbek.

### 6.3 Voice before language selection

1. Send `/start`.
2. Do **not** choose a language.
3. Send a voice message.

Expected:

- The bot asks you to choose a language.
- It should not transcribe or evaluate the voice answer.

### 6.4 Voice before part/question selection

1. Send `/start`.
2. Choose a language.
3. Do **not** choose an IELTS part.
4. Send a voice message.

Expected:

- The bot asks you to choose an IELTS Speaking part.
- It should not evaluate the voice answer.

### 6.5 Part selection failure handling

To test OpenAI question generation errors manually:

1. Stop the bot.
2. Put an invalid `OPENAI_API_KEY` in `.env`.
3. Start the bot.
4. Go through `/start` → language → part.

Expected:

- The bot shows a friendly question generation error.
- The student remains able to choose a part again.

Restore the valid OpenAI key after this test.

### 6.6 Feedback failure handling

To test feedback-generation errors:

1. Start with a valid OpenAI key.
2. Generate a question successfully.
3. Stop the bot.
4. Change `OPENAI_API_KEY` to an invalid value.
5. Start the bot again.

Because student sessions are in memory, this restart clears the session. To simulate this case without restarting, temporarily revoke or break the key while the bot is running, then send the voice answer.

Expected:

- The bot shows a friendly feedback error.
- The student can send the voice answer again for the same generated question if the session is still active.

---

## 7. Test teacher flow regression

Use a group admin/creator account.

### 7.1 Start teacher panel

1. Send `/start` in private chat.

Expected:

- The teacher panel appears.
- The bot does not ask for student language selection.

### 7.2 Single teacher audio

1. Send one voice message with an English answer.
2. Wait 30 seconds.

Expected:

- The bot processes the audio.
- It sends the overview.
- It shows detail buttons:
  - authenticity
  - grammar
  - vocabulary
  - ideas
  - finish

### 7.3 Multiple teacher audio batch

1. Send two or three voice messages within 30 seconds.
2. Wait after the final message.

Expected:

- The bot resets the timer after each new audio.
- The bot combines the transcribed parts.
- The teacher receives one combined analysis.

---

## 8. Test group moderation

Use a non-admin account in a configured allowed group.

### 8.1 Profanity moderation

1. Send a message containing a banned word from the moderation lists.

Expected:

- The bot deletes the message if it has permission.
- The bot bans the user if it has permission.
- The bot sends a ban reason to the group.

### 8.2 Admin exemption

1. Make your test account an admin.
2. Send the same kind of message again.

Expected:

- The bot ignores admin/creator messages in moderation.

---

## 9. Common local problems and fixes

### `Conflict: terminated by other getUpdates request`

Cause: another local/server copy of the bot is running.

Fix:

- Stop every bot process.
- Make sure the deployed server service is stopped if using the same token.
- Wait 5-10 seconds.
- Run `python -m bot.bot` again.

### Bot says user has no access even though user is in a group

Check:

- The group ID in `.env` exactly matches the value from `getUpdates`.
- Supergroup IDs include the `-100` prefix.
- The bot is a member of that group.
- You restarted the bot after editing `.env`.
- If using several groups, `GROUP_IDS` is comma-separated.

### Student is treated as teacher

This is expected if the user is admin/creator in **any** allowed group. Remove admin rights or test with another account.

### Teacher is treated as student

Check:

- The user is admin/creator in at least one allowed group.
- The correct group is in `GROUP_IDS`.
- The bot can call Telegram `getChatMember` for that group.

### FFmpeg errors

Check:

```bash
ffmpeg -version
```

If not installed:

- Ubuntu/Debian: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: `winget install ffmpeg`

### Audio files are not saved or deleted

Check:

- `VIDEO_SAVING_PATH=savings` exists or can be created.
- The user running the bot has write permissions in the repository folder.

### OpenAI errors

Check:

- `OPENAI_API_KEY` is valid.
- The key has access to `gpt-4o` and `whisper-1`.
- The account has available quota.
- Your network can reach OpenAI APIs.

---

## 10. Minimal full local checklist

Run through this list before considering the change locally verified:

- [ ] `python --version` is 3.11 or 3.12.
- [ ] `ffmpeg -version` works.
- [ ] `.env` contains valid `BOT_TOKEN`.
- [ ] `.env` contains valid `OPENAI_API_KEY`.
- [ ] Group IDs were collected with `getUpdates`, not copied from a helper bot.
- [ ] `.env` contains correct `GROUP_ID` or `GROUP_IDS`.
- [ ] `python -m bot.bot` starts without errors.
- [ ] Outsider account is denied.
- [ ] Student account sees language selection.
- [ ] Student can choose Russian and receive Russian feedback.
- [ ] Student can choose Uzbek and receive Uzbek feedback.
- [ ] Student voice before part selection is rejected with guidance.
- [ ] Teacher/admin account still sees teacher flow.
- [ ] Teacher detail buttons still work.
- [ ] Group moderation still works if the bot has admin permissions.
