# --- Stage 1: Builder ---
# This stage creates a self-contained virtual environment with all our dependencies.
FROM python:3.11-slim AS builder

# Set best-practice environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a virtual environment
RUN python -m venv /opt/venv

# Activate the virtual environment for subsequent RUN commands
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip within the venv. This now runs using the venv's pip.
RUN pip install --upgrade pip

# Copy and install requirements into the virtual environment
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Stage 2: Final Image ---
# This stage builds the final, secure, and lean production image.
FROM python:3.11-slim

# Set environment variables for the final image
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a dedicated, non-root user for the application
RUN groupadd --system app && useradd --system --gid app app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application code and set ownership
WORKDIR /home/app
COPY --chown=app:app . .

# Set the PATH to use the binaries from our virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Switch to the non-root user before running the application
USER app

# Expose the port
EXPOSE 8080

# The command to run the application. It will find 'gunicorn' in the venv's PATH.
CMD ["gunicorn", "-w", "4", "--threads", "8", "-b", "0.0.0.0:8080", "main:app"]