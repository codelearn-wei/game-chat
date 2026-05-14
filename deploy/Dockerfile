FROM python:3.11-slim

WORKDIR /app

# Install dependencies
# build context = game_chat/  所以路径从 backend/ 开始
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy web demo
COPY web_demo/ /app/web_demo

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

# 生产时通过 -e DEEPSEEK_API_KEY=sk-xxx 或 .env 文件传入
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
