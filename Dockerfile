FROM python:3.9-slim

WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies and clean up cache
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache

# Copy the application code
COPY . .

# Set environment variables
ENV CONFIG_PATH=/app/config.yaml
ENV HOST=0.0.0.0
ENV PORT=16379
ENV DEBUG=false

# Clean up unnecessary files
RUN rm -rf /app/tests /app/.git /app/.gitignore /app/build_docker.sh

# Set the container's startup command
CMD ["python", "run.py"]
