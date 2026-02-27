# 🔐 MeDo Automation - Secure Setup Guide

## 📋 Overview

This system includes:
- **Frontend**: Secure web interface with access key authentication
- **Backend + Discord Bot**: Combined in one process (JSON file storage)

---

## 🚀 Quick Start (Simplified!)

### 1. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **"New Application"** → Name it "MeDo Bot"
3. Go to **"Bot"** tab → Click **"Reset Token"** → **Copy token**
4. Enable these under **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
   - ✅ Presence Intent
5. Go to **"OAuth2"** → Copy **Application ID** (Client ID)
6. Go to **"Bot"** → Enable **"Public Bot"** (optional)

### 2. Invite Bot to Your Server

Use this URL (replace `YOUR_CLIENT_ID`):
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

### 3. Setup Bot + Backend

```bash
cd medo/bot

# Install dependencies
npm install

# Create .env file
cp ../.env.example .env

# Edit .env with your Discord token
nano .env
```

**.env file:**
```env
PORT=3000
ALLOWED_ORIGINS=https://your-vercel-url.vercel.app,http://localhost:5173
DISCORD_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_bot_client_id_here
```

### 4. Start Bot + Backend

```bash
# Development (auto-reload)
npm run dev

# Production
npm start
```

**You'll see:**
```
✅ Discord bot logged in as YourBot#1234
📊 Serving 1 servers
🔄 Registering slash commands...
✅ Slash commands registered globally
📁 Data files initialized
🔒 Backend API running on port 3000
📁 Data directory: /path/to/data
🌐 Backend API available at http://localhost:3000
```

---

## 🎮 Discord Bot Commands

All commands are **restricted to authorized users only** (configured in bot/index.js).

### `/generate-key`
Generate a new access key.

**Usage:**
```
/generate-key duration:2h user:@username
```

**Options:**
- `duration`: `2m` (minutes), `1h` (hours), `1d` (days)
- `user`: (Optional) Assign key to specific user

### `/list-keys`
Show all active access keys.

### `/revoke-key`
Revoke an access key immediately.

**Usage:**
```
/revoke-key key:ABCD-EFGH-IJKL-MNOP
```

### `/key-stats`
View statistics for a specific key.

**Usage:**
```
/key-stats key:ABCD-EFGH-IJKL-MNOP
```

---

## 🔒 Security Features

### Frontend Security
- ✅ Access key required before GitHub token
- ✅ Browser fingerprinting prevents key sharing
- ✅ Keys expire after set duration
- ✅ One key per device
- ✅ HTTPS enforced
- ✅ XSS protection headers
- ✅ Frame protection (clickjacking prevention)

### Backend Security
- ✅ CORS restrictions
- ✅ Secure key hashing (SHA-256)
- ✅ JSON file storage (no external DB needed)
- ✅ Input validation
- ✅ Error handling
- ✅ Security headers

### Discord Bot Security
- ✅ Authorized users only (whitelist)
- ✅ Ephemeral responses (commands hidden)
- ✅ DM support for key delivery
- ✅ Secure token storage via .env

---

## 🌐 Deploy to Vercel

### Frontend (Vercel)

1. Push code to GitHub
2. Go to https://vercel.com/new
3. Import your repository
4. Set **Root Directory**: `frontend`
5. Deploy

### Backend + Bot (Railway/Render)

**Railway:**
1. Create new project
2. Connect GitHub repo
3. Set **Root Directory**: `bot`
4. Add environment variables from `.env`
5. Deploy

**Update frontend** with backend URL in `index.html`:
```javascript
const API_BASE = 'https://your-backend.railway.app';
```

---

## 📊 Data Storage

All data is stored in `bot/data/` (created automatically):

- `keys.json`: Access keys database
- `usage.json`: Key usage statistics

**Backup regularly!**

---

## 🔧 Authorized Users

Edit `bot/index.js` to add/remove authorized users:

```javascript
const AUTHORIZED_USERS = [
    '1033929243215806594',  // qvfear
    '1326206060020629577',  // Admin 2
    'YOUR_USER_ID_HERE'     // Add more
];
```

**Find your Discord User ID:**
1. Enable Developer Mode in Discord (Settings → Advanced)
2. Right-click your username → Copy ID

---

## 🐛 Troubleshooting

### Bot not responding to commands
- Check bot has proper permissions
- Verify bot is online
- Check console for errors
- Re-run `node index.js`

### "Invalid access key" error
- Key may be expired
- Key already used on different device
- Contact admin to generate new key

### Backend won't start
- Check `.env` file exists
- Verify port 3000 is available
- Check Node.js version (16+)

### Frontend can't connect to backend
- Check CORS settings in backend `.env`
- Verify backend URL in frontend
- Check network tab for errors

### Bot shows error on startup
- Verify Discord token is correct
- Check all intents are enabled in Discord Developer Portal
- Ensure bot is invited to at least one server

---

## 📝 Example Workflow

1. **Admin generates key** in Discord:
   ```
   /generate-key duration:1h user:@user
   ```

2. **User receives key** via DM with instructions

3. **User visits website**:
   - Enters access key → Validated ✅
   - Enters GitHub token → Automation starts!

4. **After 1 hour**: Key expires, user must request new one

---

## 🎯 Key Expiration Examples

| Duration | Command | Expires In |
|----------|---------|------------|
| 2 minutes | `/generate-key duration:2m` | 120 seconds |
| 30 minutes | `/generate-key duration:30m` | Half hour |
| 1 hour | `/generate-key duration:1h` | 60 minutes |
| 6 hours | `/generate-key duration:6h` | Half day |
| 1 day | `/generate-key duration:1d` | 24 hours |
| 7 days | `/generate-key duration:7d` | 1 week |

---

## 🔑 Best Practices

1. **Short durations**: Give keys for 1-2 hours max for trial users
2. **Monitor usage**: Use `/list-keys` regularly
3. **Revoke unused**: Clean up old/unused keys
4. **One per user**: Assign keys to specific users
5. **Backup data**: Copy `bot/data/` folder regularly

---

## 🎉 You're Done!

**Single command to run everything:**
```bash
cd medo/bot
npm start
```

This starts both the Discord bot AND the backend API!

---

**Made by qvfear** | Discord: qvfear
