FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Chromium browser is installed
RUN playwright install chromium

# Copy app files
COPY . .

# Environment configuration
ENV PORT=8787
ENV PYTHONUNBUFFERED=1
EXPOSE 8787

# Start the Telegram Link Opener server
CMD ["python3", "server.py"]
