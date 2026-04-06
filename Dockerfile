FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better caching)
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r server/requirements.txt

# Copy rest of the code
COPY . .

# Set PYTHONPATH so imports work
ENV PYTHONPATH="/app"

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]