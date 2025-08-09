# Use a slim Python base image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the application code
COPY main.py .

# Define environment variable for the port (optional, Cloud Run uses 8080 by default)
ENV PORT 8080

# Run the application
CMD ["python", "main.py"]