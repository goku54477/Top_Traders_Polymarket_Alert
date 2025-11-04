# Railway Configuration Guide

## ✅ Required Environment Variables

Update these environment variables in your Railway dashboard:

### 1. DOME_API_KEY
```
bf29312e-2fdd-478f-b3eb-cf117b9f8b94
```

### 2. TELEGRAM_BOT_TOKEN
```
8292495956:AAHt2g7zQucKAaGZrygtTZ_5Cq8tPpxp43Q
```

### 3. TELEGRAM_CHAT_ID ⚠️ **IMPORTANT - FIX THIS!**
```
-1002697342092
```
**Note:** Make sure this is exactly `-1002697342092` (with the `2` at the end)

### 4. POLL_INTERVAL_MIN (Optional)
```
60
```

## 📋 How to Update on Railway

1. Go to your Railway dashboard
2. Select your service (Esports Odds Monitor)
3. Click on the **Variables** tab
4. For each variable above:
   - If it exists: Click the variable name → Edit → Update the value → Save
   - If it doesn't exist: Click **+ New Variable** → Add name and value → Save

## 🔍 Verification Checklist

After updating, verify:

- [ ] `TELEGRAM_CHAT_ID` is exactly `-1002697342092` (not `-100269734209`)
- [ ] All 4 environment variables are set
- [ ] No extra spaces or quotes around the values
- [ ] Redeploy the service after making changes

## 🚀 After Updating

1. Railway should automatically redeploy, or you can manually trigger a redeploy
2. Check the logs to see:
   - ✅ "Telegram chat validated successfully"
   - ✅ "Test message sent successfully to Telegram chat"
   - ✅ "Starting Esports Odds Alert Bot..."

## ⚠️ Common Issues

- **"Chat not found"**: Check that `TELEGRAM_CHAT_ID` is exactly `-1002697342092`
- **"Placeholder values detected"**: Ensure all environment variables are set (not using defaults)
- **Rate limiting**: Normal behavior - the bot handles this automatically

## 📊 Test Results (Local)

- ✅ Chat ID `-1002697342092` validated successfully
- ✅ 9 alerts sent to Telegram group
- ✅ Bot is working correctly

