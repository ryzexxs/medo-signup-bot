# MeDo Automation Bot

Automated account creation tool for MeDo.dev

## ⚡ Quick Start

### Run via GitHub Actions

1. Go to **Actions** tab
2. Select **"MeDo Automation"**
3. Click **"Run workflow"**
4. Fill in:
   - **Number of accounts**: How many to create
   - **Workers**: Parallel browsers (1-5)
   - **Invite link**: Your referral link
5. Click **"Run workflow"**
6. Watch live logs and get results!

## 📁 Files

- `medo.py` - Main automation script
- `requirements.txt` - Python dependencies
- `.github/workflows/medo-automation.yml` - GitHub Actions workflow

## 🖥 Local Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run interactively
python medo.py

# Or with arguments
python medo.py -t 10 -w 3 -l "https://medo.dev/?invitecode=user-xxxxx"
```

## ⚙️ Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `-t, --total` | Number of accounts | 10 |
| `-w, --workers` | Parallel workers | 3 |
| `-l, --invite-link` | Invite link | Prompt |
| `-v, --verbose` | Verbose logging | False |

## 📊 GitHub Actions Limits

- **Free tier**: 2000 minutes/month
- **Max job duration**: 6 hours
- **Time per account**: ~50 seconds
- **Accounts per month**: ~2500 (with 10 accounts/run)

## ⚠️ Disclaimer

This tool is for **educational and testing purposes only**. Use responsibly and comply with MeDo.dev's Terms of Service.

---

**Made by qvfear** | Discord: qvfear
