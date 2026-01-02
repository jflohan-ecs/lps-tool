# LPS Tool - Deployment Guide

## Quick Deploy to Render (Free Tier)

### Prerequisites
- GitHub account with lps-tool repository
- Render account (free - create at https://render.com)

### Step-by-Step Deployment

#### 1. Create Render Account
1. Go to https://render.com
2. Sign up with GitHub (connects automatically)
3. Authorize Render to access your repositories

#### 2. Deploy the Application
1. Click **"New +"** → **"Web Service"**
2. Connect your `lps-tool` repository
3. Configure:
   - **Name:** `lps-tool` (or your choice)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free` (for testing)
4. Click **"Create Web Service"**

#### 3. Add PostgreSQL Database
1. Click **"New +"** → **"PostgreSQL"**
2. Configure:
   - **Name:** `lps-db`
   - **Database:** `lps_production`
   - **User:** `lps_user`
   - **Instance Type:** `Free`
3. Click **"Create Database"**
4. Once created, copy the **Internal Database URL**

#### 4. Connect Database to Application
1. Go back to your `lps-tool` web service
2. Click **"Environment"** tab
3. Add environment variable:
   - **Key:** `DATABASE_URL`
   - **Value:** [Paste the Internal Database URL]
4. Click **"Save Changes"**
5. Service will auto-redeploy

#### 5. Access Your Application
After deployment completes (2-3 minutes):
- Your app will be at: `https://lps-tool-XXXX.onrender.com`
- Visit the URL to see your LPS Tool live!

---

## Local Development vs Production

### Local (Your Computer)
```bash
# Uses SQLite database (lps.db file)
python -m uvicorn app.main:app --reload
# Access at: http://localhost:8000
```

### Production (Render)
```bash
# Uses PostgreSQL database (from DATABASE_URL env var)
# Automatically configured via render.yaml
# Access at: https://your-app.onrender.com
```

---

## Deployment Architecture

```
GitHub Repository
       ↓ (push code)
   Render Platform
       ↓
   Web Service (FastAPI app)
       ↓
   PostgreSQL Database
       ↓
   Users access via HTTPS URL
```

### What Happens on Deploy:
1. Render pulls latest code from GitHub
2. Installs dependencies from `requirements.txt`
3. Creates PostgreSQL database
4. Sets DATABASE_URL environment variable
5. Runs `uvicorn app.main:app`
6. App creates database tables automatically (on first run)
7. Service is live at your Render URL

---

## Post-Deployment Checklist

### Immediate (Day 1)
- [ ] Visit your URL and verify it loads
- [ ] Create a test work item
- [ ] Add constraints and test the full spine
- [ ] Verify data persists (refresh page, data still there)

### Within First Week
- [ ] Share URL with 2-3 test users
- [ ] Collect feedback on usability
- [ ] Monitor for errors in Render logs
- [ ] Test from different devices/browsers

### Phase 2 Planning
- [ ] List polish items based on user feedback
- [ ] Prioritize: UI improvements vs. authentication vs. integrations
- [ ] Plan next deployment cycle

---

## Common Issues & Solutions

### "Site can't be reached"
- Check Render dashboard - service may still be deploying
- Wait 2-3 minutes for initial deployment
- Check Render logs for errors

### "Internal Server Error"
- Check Render logs: Dashboard → Your Service → Logs
- Common causes:
  - DATABASE_URL not set correctly
  - Database not connected
  - Missing environment variable

### Data Not Persisting
- If using free tier, database may spin down after inactivity
- First request after sleep may be slow (database waking up)
- Consider upgrading to paid tier for 24/7 availability

### Code Changes Not Appearing
- Render auto-deploys when you push to GitHub main branch
- Manual redeploy: Dashboard → Your Service → "Manual Deploy"
- Check "Events" tab to see deployment status

---

## Upgrading / Making Changes

### Change Code
1. Edit files locally
2. Test locally: `python -m uvicorn app.main:app --reload`
3. Commit: `git add . && git commit -m "Your change"`
4. Push: `git push`
5. Render auto-deploys (watch Events tab)

### Change Database Schema
If you modify models in `app/models/`:
1. Changes apply automatically on next deploy
2. SQLAlchemy auto-creates new tables/columns
3. **Warning:** Removing columns loses data - plan migrations carefully

### Rollback
If something breaks:
```bash
git revert HEAD  # Undo last commit
git push         # Deploy previous version
```

---

## Cost Considerations

### Free Tier (Current)
- ✅ Good for: Testing, demos, small teams (<10 users)
- ⚠️ Limitations:
  - Spins down after 15 min inactivity (first request slow)
  - 750 hours/month free compute
  - Limited database storage

### Paid Tier ($7-25/month)
- ✅ 24/7 uptime (no spin down)
- ✅ More compute power
- ✅ More database storage
- ✅ Better performance
- Upgrade when: >10 daily users or need guaranteed uptime

---

## Security Notes (Current State)

### What's Secure:
- ✅ HTTPS automatic (Render provides SSL)
- ✅ Database password-protected
- ✅ Environment variables encrypted
- ✅ Code on private GitHub repo

### What's NOT Yet Implemented:
- ❌ User authentication (anyone with URL can access)
- ❌ Rate limiting (could be spammed)
- ❌ Audit log viewing (exists but not exposed)

### Quick Security Additions (Phase 2):
1. **Basic Password Protection:**
   - Add HTTP Basic Auth middleware
   - Single shared password for all users
   - 1-2 hours work

2. **User Accounts:**
   - Proper login system with email/password
   - User-specific data views
   - 3-5 days work

---

## Next Steps After Launch

1. **Validate with Users** (Week 1)
   - Get real feedback
   - Document pain points
   - Observe usage patterns

2. **Prioritize Improvements** (Week 2)
   - Based on actual needs, not assumptions
   - Focus on highest-value changes

3. **Iterate** (Ongoing)
   - Small, frequent improvements
   - Test each change with users
   - Keep core logic stable (constitution)

---

**Your app is designed for change. The hard part (state machine) is done. Everything else is refinement.**
