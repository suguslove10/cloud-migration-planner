from flask import Flask, render_template, request, jsonify
import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
load_dotenv()
API_GATEWAY_URL = os.getenv('API_GATEWAY_URL')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': 'No file provided'}), 400

        # Read and parse JSON data
        data = json.loads(file.read())
        logger.debug(f"Input data: {json.dumps(data, indent=2)}")
        
        # Call API Gateway endpoint
        response = requests.post(
            f"{API_GATEWAY_URL}/analyze",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        logger.debug(f"API Response status: {response.status_code}")
        logger.debug(f"API Response: {response.text}")
        
        if response.status_code != 200:
            return jsonify({'error': f'Analysis failed: {response.text}'}), 500
            
        analysis_result = response.json()
        
        # Call cost estimation
        for server in analysis_result['servers']:
            cost_response = requests.post(
                f"{API_GATEWAY_URL}/estimate",
                json={
                    'serverData': server['serverData'],
                    'migrationStrategy': server['migrationStrategy']
                },
                headers={'Content-Type': 'application/json'}
            )
            if cost_response.status_code == 200:
                server['costAnalysis'] = cost_response.json()
        
        # Call roadmap generation
        roadmap_response = requests.post(
            f"{API_GATEWAY_URL}/roadmap",
            json=analysis_result,
            headers={'Content-Type': 'application/json'}
        )
        if roadmap_response.status_code == 200:
            analysis_result['roadmap'] = roadmap_response.json()
        
        return jsonify(analysis_result)
        
    except Exception as e:
        logger.error(f"Error in analyze endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Using API Gateway URL: {API_GATEWAY_URL}")
    app.run(debug=True)