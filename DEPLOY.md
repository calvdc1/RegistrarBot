# How to Host Your Bot 24/7 on Render

To keep your bot running 24/7, you need to host it on a cloud server.

## 🚨 IMPORTANT: Data Persistence 🚨
This bot uses a local SQLite database (`attendance.db`). 
- **On Render's Free Tier**, the filesystem is **ephemeral**. This means **all attendance data will be deleted** every time the bot restarts or redeploys.
- **To save data permanently**, you must use a **Render Disk** (Paid Feature) or switch to an external database.

## Method 1: Automatic Deployment (Recommended for Persistence)
This method uses the included `render.yaml` file to set up a Persistent Disk automatically. **(Requires Render Paid Plan)**

1. **Fork/Clone this Repository** to your GitHub.
2. Go to [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** -> **Blueprint**.
4. Connect your repository.
5. Render will automatically detect the `render.yaml` configuration.
6. Click **Apply**.
7. **Environment Variables**: Enter your `DISCORD_TOKEN` in the dashboard if prompted, or add it manually in the **Environment** tab after creation. Render blueprint placeholders created with `sync: false` do **not** include a value automatically.
8. If the token is missing, the service can stay online for health checks, but the bot will **not** connect to Discord until `DISCORD_TOKEN` is configured and the service is redeployed.

## Method 2: Free Tier (No Persistence)
If you only need the bot for testing and don't care about losing data on restart:

1. **Create a New Web Service** on Render.
2. Connect your GitHub repo.
3. **Settings**:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
4. **Environment Variables**:
   - `DISCORD_TOKEN`: Your bot token.
   - `PYTHON_VERSION`: `3.10.12`

## Prevent "Sleeping" (Free Tier Only)
Free servers sleep after 15 minutes. Use [UptimeRobot](https://uptimerobot.com/) to ping your Render URL every 5 minutes.


## How to Update/Redeploy
When you make changes to your code (like the recent timezone update):

1. **Save** your files.
2. **Push** your changes to GitHub.
3. **Render** will automatically detect the new code and start redeploying within a minute.
4. You can check the progress in the "Events" or "Logs" tab on your Render dashboard.

If it doesn't deploy automatically:
1. Go to your service on Render.
2. Click the **"Manual Deploy"** button.
3. Select **"Deploy latest commit"**.
