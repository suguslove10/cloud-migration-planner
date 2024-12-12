#!/bin/bash

#set -e  # Exit on error
#set -x  # Print commands as they execute

# Create virtual environment if it doesn't exist
#if [ ! -d "venv" ]; then
    #python -m venv venv
#fi

# Activate virtual environment
#source venv/bin/activate

# Install requirements
#pip install -r requirements.txt

# Run infrastructure setup
#python backend/infrastructure.py

# Run application
#python frontend/app.py



API_GATEWAY_URL=https://ee8ii30rxh.execute-api.ap-south-1.amazonaws.com/prod
AWS_REGION=ap-south-1
FLASK_ENV=development
