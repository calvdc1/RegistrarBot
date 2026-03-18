# Registrar Bot

A comprehensive Discord bot for managing attendance, user nicknames, and role-based access control. Designed for ease of use with automated reporting, professional designs, and persistent data storage.

## Features

### 📅 Advanced Attendance System
- **Time Window Mode**: Set specific hours (e.g., 8:00 AM - 5:00 PM) for attendance.
- **Time Zone Support**: Automatically uses **Philippines Time (UTC+8)** for all schedules.
- **Deadline Display**: Reports clearly show the submission deadline.
- **Role-Based Permissions**: Restrict `present` to specific roles (e.g., "Student" or "Staff") using `!setpermitrole`.
- **Automated Reports**:
  - Live-updating **Daily Attendance Report** embed in your chosen channel.
  - Shows Date, Time, Deadline, Status (OPEN/CLOSED), and Present/Absent/Excused lists.
- **Status Tracking**:
  - **Present**: Users marked present (automatically or manually).
  - **Absent**: Users who missed the window (auto-marked) or manually marked.
  - **Excused**: Users excused by admins with a reason.
- **Setup Confirmation**: Smart notification when all required configurations are complete.

### 🔔 Smart Notifications
- **Auto-Absent DMs**: Users who miss the attendance window are automatically marked Absent and receive a detailed Direct Message.
- **Status Alerts**:
  - **Present**: Users receive a gold-themed DM confirming their attendance.
  - **Excused**: Users receive a neutral white DM including the reason and time.
  - **Absent**: Users receive a red DM notification when marked absent (auto or manual).
- **Professional Design**: All DMs and Reports feature the server's icon, branded colors, and timestamps.

### 🏆 Attendance Leaderboard
- **Per-Member Stats**: Tracks Present, Absent, and Excused counts in SQLite.
- **Leaderboard Command**: `!leaderboard` / `!attendance_leaderboard` shows:
  - A gold embed with server branding.
  - A table: `Rank | Member | Present / Absent / Excused`.
- **Daily Reset**: `!resetattendance` clears daily records **and resets all leaderboard counts back to 0** while keeping your config.

### 📌 Sticky Messages
- **Channel Stickies**: Use `!stick <text>` to keep one sticky message at the bottom of a channel.
- **Non-Duplicating**: The sticky message is only recreated if it is deleted.
- **Smart Cleanup**: In sticky channels, plain-text messages are auto-deleted, but messages with images/photos are kept.
- **Remove Sticky**: Use `!removestick` to disable the sticky for a channel.

### 📝 Auto-Nickname
- **Standardized Format**: automatically adds a suffix (e.g., `[𝙼𝚂𝚄𝚊𝚗]`) to nicknames.
- **Enforcement**: Options to enforce naming conventions on join or role changes.

### 💾 Persistence
- **Database Storage**: SQLite database ensures data survives restarts.
- **Railway + Cloudflare Ready**: Includes Railway health checks, Cloudflare-friendly HTTP endpoints, and first-class Cloudflare Containers deployment files.
- **Render.com Ready**: Configured for easy deployment with persistent disk support.

---

## 🚀 Setup Guide

### 1. Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your bot token:
   ```
   DISCORD_TOKEN=your_token_here
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

### 2. Configuration (In Discord)
Run these commands in your server to set up the bot. **The bot will notify you when setup is complete!**

1.  **Reset (Optional)**: Start fresh if needed.
    ```
    !resetattendance
    ```
2.  **Set Time Window**:
    ```
    !settime 8:00am - 5:00pm
    ```
3.  **Assign Report Channel**:
    ```
    !assignchannel #attendance-reports
    ```
    *To disable reporting, use:* `!assignchannel remove`
4.  **Configure Roles**:
    ```
    !presentrole @Present
    !absentrole @Absent
    !excuserole @Excused
    ```
5.  **Set Permitted Role** (Who can use `present`?):
    ```
    !setpermitrole @Student
    ```
6.  **Set Present Channel** (Where they can say `present`?):
    ```
    !channelpresent #attendance-channel
    ```

🎉 **Once all steps are done, the bot will send a "Setup Complete" confirmation!**

After setup, use:

- `!attendance` to post or refresh the Daily Attendance Report.
- `present`, `absent`, or the attendance buttons in the attendance channel to update the report. Once a user is marked present, absent, or excused for the session, they cannot switch to another status until an admin resets them.
- `!leaderboard` to show the gold Attendance Leaderboard.

---

## 📚 Command Reference

### User Commands
| Command | Description |
| :--- | :--- |
| `present` / `absent` | Mark yourself as present or absent (requires Permitted Role & Active Window). Once submitted, you cannot switch to another status until an admin resets you. |
| `!nick <Name>` | Change your nickname (suffix added automatically). |
| `!attendance` | View the current attendance status. |

### Admin / Staff Commands
| Command | Description |
| :--- | :--- |
| **Attendance** | |
| `!present @User` | Manually mark a user as present. |
| `!absent @User` | Mark a user as absent (Sends DM). |
| `!excuse @User <Reason>` | Excuse a user with a reason (Sends DM). |
| `!removepresent @User` | Reset a user's status. |
| `!removereport` | Instantly delete the current attendance report message. |
| `!leaderboard` | Show the attendance leaderboard (Present / Absent / Excused). |
| **Configuration** | |
| `!settings` | Open interactive settings dashboard. |
| `!settime <Start> - <End>` | Set daily attendance window (PH Time). |
| `!assignchannel #channel` | Set channel for live reports. |
| `!assignchannel remove` | Disable automatic attendance reporting. |
| `!setpermitrole @Role` | Set which role is allowed to use `!present`. |
| `!resetpermitrole` | Remove the permission restriction. |
| `!channelpresent #channel` | Restrict `present` messages to a single channel. |
| `!presentrole @Role` | Set the role given for Present status. |
| `!absentrole @Role` | Set the role given for Absent status. |
| `!excuserole @Role` | Set the role given for Excused status. |
| `!resetattendance` | **Full Wipe**: Clears all records, removes status roles from users, and resets settings. |

---

## ☁️ Deployment

### Railway + Cloudflare

This bot now includes a production-friendly HTTP health server that works well on [Railway](https://railway.com) and when a Railway app is placed behind [Cloudflare](https://www.cloudflare.com/) DNS/proxying for a custom domain.

1.  Create a new Railway project and deploy this repository. Railway will detect Python automatically, and `railway.json` configures `python bot.py` plus a `/healthz` health check.
2.  In Railway variables, set:
    - `DISCORD_TOKEN` = your Discord bot token
    - `DB_FILE` = `/data/attendance.db` if you attach a Railway volume, or leave it unset to use the local filesystem
3.  If you need persistent attendance data, attach a Railway Volume and mount it at `/data`.
4.  (Optional) In Cloudflare DNS, point a custom domain or subdomain to your Railway hostname. The built-in `/`, `/healthz`, and `/readyz` endpoints return JSON and disable caching, which makes them safe for Cloudflare proxying and uptime checks.
5.  If Cloudflare proxying causes issues during first setup, temporarily switch the DNS record to **DNS only** until SSL finishes provisioning, then re-enable proxying if desired.

### Cloudflare Containers

This repository can now deploy directly to the [Cloudflare global network](https://developers.cloudflare.com/containers/) using **Cloudflare Containers**. The repo includes a `Dockerfile`, `wrangler.jsonc`, and a Worker entrypoint that proxies requests to a named container instance, injects `DISCORD_TOKEN` into the container runtime, and uses a one-minute Cron Trigger to keep the bot container warm enough to preserve the Discord connection.

1. Install Docker, Node.js, and npm locally. Cloudflare's official flow builds the container image with Docker during `wrangler deploy`.
2. Install JavaScript dependencies:
   ```bash
   npm install
   ```
3. Authenticate Wrangler:
   ```bash
   npx wrangler login
   ```
4. Add your Discord token as a Cloudflare Worker secret:
   ```bash
   npx wrangler secret put DISCORD_TOKEN
   ```
5. Deploy to Cloudflare:
   ```bash
   npm run cf:deploy
   ```
6. Check rollout status if needed:
   ```bash
   npx wrangler containers list
   npx wrangler containers images list
   ```

**Important persistence note:** Cloudflare Containers currently provide **ephemeral disk**, so the bundled SQLite database will reset whenever the container is replaced or restarted. For production attendance history on Cloudflare, move persistence to an external database or storage service before relying on long-term data retention.

### Render.com

This bot is configured for deployment on [Render](https://render.com).

1.  Fork this repository to your GitHub.
2.  Create a new **Web Service** on Render.
3.  Connect your GitHub repository.
4.  Render should automatically detect the `render.yaml` configuration.
    *   **Runtime**: Python 3
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `python bot.py`
5.  Add your `DISCORD_TOKEN` in the **Environment Variables** section of your Render service. If you created the service from `render.yaml`, note that the placeholder secret is declared with `sync: false`, so you still need to provide the real token in Render.
6.  Until `DISCORD_TOKEN` is set, the health-check web server can still respond, but the bot itself will not log in to Discord.
7.  (Optional) Add a **Persistent Disk** mounted at `/data` if you want the database to survive redeploys.

### Vercel

Vercel is optimized for web apps and serverless APIs, not long-running processes. To run this Discord bot via Vercel you typically:

1. Host the bot code in a Git repository (GitHub/GitLab).
2. Create a small web/API entry on Vercel (for status page or simple HTTP endpoint).
3. Run the actual bot process on a worker/VM provider (Render, Railway, a VPS, etc.), and connect it to the same repository.

To update the bot after making code changes:

1. Commit and push your changes to the repository connected to Vercel.
2. Trigger a new deployment from the Vercel dashboard (or let it auto-deploy on push).
3. Ensure that `DISCORD_TOKEN` and any other environment variables are set in Vercel if you expose HTTP endpoints.

For always-on Discord presence, keep the Python process running on a platform that supports long-running background workers (e.g., Render) and use Vercel only for optional web-facing parts.
