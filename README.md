# ✈️ Telegram Link Opener

A web app that resolves Telegram bot verification links, URL shorteners, WPSafelink gates, countdown timers, and ad-blocker detection pages server-side using headless Playwright browser automation, and gives you the direct destination link with zero ads.

---

## 🚀 Deploying to the Cloud (Render / Railway)

Because Telegram Link Opener uses **headless Chromium (Playwright)** and needs ~60–90 seconds to bypass multi-step countdown gates, standard serverless platforms like Vercel (which cap execution at 10 seconds) will timeout. Instead, deploy it using Docker on **Render** or **Railway** for free.

### Option A: Deploy on Render (Recommended & Free)
1. Push this folder to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<your-username>/telegram-link-opener.git
   git push -u origin main
   ```
2. Go to [render.com](https://render.com) and click **New +** → **Web Service**.
3. Connect your GitHub repository.
4. Select **Docker** as the runtime (Render will automatically detect the `Dockerfile` and `render.yaml`).
5. Choose the **Free** instance type and click **Deploy Web Service**.
6. Render will build the container and provide your live public URL (e.g. `https://telegram-link-opener.onrender.com`).

---

### Option B: Deploy on Railway
1. Go to [railway.app](https://railway.app).
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your repository. Railway will detect the `Dockerfile` and deploy automatically.
4. Go to **Settings** → **Networking** → **Generate Domain** to get your public URL.

---

## 💻 Running Locally

### Prerequisites
- Python 3.10+
- Playwright

### Setup & Run
```bash
pip install -r requirements.txt
playwright install chromium
python3 server.py
```
Then open [http://127.0.0.1:8787](http://127.0.0.1:8787) in your browser.
