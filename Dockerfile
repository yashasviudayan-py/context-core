# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.12-slim

# Apply security updates
RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r vault && useradd -r -g vault -u 1000 vault

# Set the working directory in the container.
WORKDIR /app

# Copy the dependency files to the working directory.
COPY pyproject.toml .python-version README.md ./

# Copy the source code to the working directory.
COPY src/ ./src

# Install the project dependencies.
RUN pip install --no-cache-dir .

# Create data directories with correct permissions
RUN mkdir -p /app/chroma_data /app/logs && \
    chown -R vault:vault /app

# Switch to non-root user
USER vault

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "from context_core.utils import check_ollama_running; exit(0 if check_ollama_running() else 1)" || exit 1

# Set the entrypoint for the container.
ENTRYPOINT ["vault"]
