# Registrar Bot

A comprehensive Discord bot for managing attendance, user nicknames, and role-based access control. Designed for ease of use with automated reporting, professional designs, and persistent data storage.

## Features

### 📅 Advanced Attendance System
- **Time Window Mode**: Set specific hours (e.g., 8:00 AM - 5:00 PM) for attendance.
- **Time Zone Support**: Automatically uses **Philippines Time (UTC+8)** for all schedules.
- **Deadline Display**: Reports clearly show the submission submission deadline.
- **Role-Based Permissions**: Restrict `!present` to specific roles (e.g., "Student" or "Staff") using `!setpermitrole`.
- **Automated Reports**: Live-updating attendance board in a dedicated channel with professional embed designs (Server Icon, Status Colors).
- **Status Tracking**:
  - **Present**: Users marked present (automatically or manually).
  - **Absent**: Users who missed the window (auto-marked) or manually marked.
  - **Excused**: Users excused by admins with a reason.
- **Setup Confirmation**: Smart notification when all required configurations are complete.

### 🔔 Smart Notifications (New!)
- **Auto-Absent DMs**: Users who miss the attendance window are automatically marked Absent and receive a detailed Direct Message.
- **Status Alerts**:
  - **Excused**: Users receive a DM with the reason and time when marked excused.
  - **Absent**: Users receive a DM notification when marked absent.
- **Professional Design**: All DMs and Reports feature the server's icon, branded colors, and timestamps.

### 📝 Auto-Nickname
- **Standardized Format**: automatically adds a suffix (e.g., `[𝙼𝚂𝚄𝚊𝚗]`) to nicknames.
- **Enforcement**: Options to enforce naming conventions on join or role changes.

### 💾 Persistence
- **Database Storage**: SQLite database ensures data survives restarts.
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
5.  **Set Permitted Role** (Who can use `!present`?):
    ```
    !setpermitrole @Student
    ```

🎉 **Once all steps are done, the bot will send a "Setup Complete" confirmation!**

---

## 📚 Command Reference

### User Commands
| Command | Description |
| :--- | :--- |
| `!present` | Mark yourself as present (requires Permitted Role & Active Window). |
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
| **Configuration** | |
| `!settings` | Open interactive settings dashboard. |
| `!settime <Start> - <End>` | Set daily attendance window (PH Time). |
| `!assignchannel #channel` | Set channel for live reports. |
| `!assignchannel remove` | Disable automatic attendance reporting. |
| `!setpermitrole @Role` | Set which role is allowed to use `!present`. |
| `!resetpermitrole` | Remove the permission restriction. |
| `!presentrole @Role` | Set the role given for Present status. |
| `!absentrole @Role` | Set the role given for Absent status. |
| `!excuserole @Role` | Set the role given for Excused status. |
| `!resetattendance` | **Full Wipe**: Clears all records, removes status roles from users, and resets settings. |

---

## ☁️ Deployment on Render

This bot is configured for deployment on [Render](https://render.com).

1.  Fork this repository to your GitHub.
2.  Create a new **Web Service** on Render.
3.  Connect your GitHub repository.
4.  Render should automatically detect the `render.yaml` configuration.
    *   **Runtime**: Python 3
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `python bot.py`
5.  **Important**: Add your `DISCORD_TOKEN` in the **Environment Variables** section of your Render service.
6.  (Optional) Add a **Persistent Disk** mounted at `/var/data` if you want the database to survive redeploys (configured in `database.py`).
