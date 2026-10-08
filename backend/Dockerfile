FROM python:3.11-slim

WORKDIR /app

# Copy requirements to backend folder context inside the container
COPY requirements.txt ./backend/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy the rest of backend source code to /app/backend/
COPY . ./backend

# Expose FastAPI server port
EXPOSE 8000

# Set PYTHONPATH environment variable to find the backend package
ENV PYTHONPATH=/app

# Start the FastAPI application with hot-reloading
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
