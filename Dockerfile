# Use a slim Python base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# This is CRITICAL for ensuring standard library logs appear promptly.
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .

# Expose the port the server will run on
EXPOSE 8080

# Run the application using the production-grade Gunicorn server
CMD ["gunicorn", "-w", "4", "--threads", "8", "-b", "0.0.0.0:8080", "main:app"]