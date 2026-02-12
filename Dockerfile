# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.12-slim

# Set the working directory in the container.
WORKDIR /app

# Copy the dependency files to the working directory.
COPY pyproject.toml .python-version README.md ./

# Copy the source code to the working directory.
COPY src/ ./src

# Install the project dependencies.
RUN pip install .

# Set the entrypoint for the container.
ENTRYPOINT ["vault"]
