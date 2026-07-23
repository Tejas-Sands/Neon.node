FROM python:3.9-slim

# Install system dependencies for Chromium, FFmpeg and node
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ffmpeg \
    chromium \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js v20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node requirements
COPY package.json ./
RUN npm install
RUN npm install @tailwindcss/oxide-linux-x64-gnu

# Copy application code
COPY . .

# Set environment variables for Remotion headless runner and real-time logs
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV REMOTION_CHROMIUM_PATH=/usr/bin/chromium
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
