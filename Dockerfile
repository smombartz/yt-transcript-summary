# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir reduces image size
# --trusted-host pypi.python.org -i http://pypi.python.org/simple can be added if there are SSL issues with pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
# This includes app.py, templates/, and static/
COPY . .

# Make port 5000 available to the world outside this container
# This is the port Gunicorn will listen on inside the container
EXPOSE 5000

# Define environment variable for Flask (optional, Gunicorn will run app:app)
# ENV FLASK_APP=app.py
# ENV FLASK_RUN_HOST=0.0.0.0

# Command to run the application using Gunicorn as the WSGI server
# Gunicorn is a production-ready server, more robust than Flask's built-in dev server.
# It will look for an 'app' instance in the 'app.py' file.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
