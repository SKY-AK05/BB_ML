#!/usr/bin/env python3
"""
Vercel Serverless Function for AnnotCheck API
Handles Flask app deployment on Vercel
"""

import json
import sys
import os
from pathlib import Path

# Add the parent directory to Python path so we can import our main app
sys.path.append(str(Path(__file__).parent.parent))

# Import the main Flask app
from annotcheck_desktop import app

# Vercel serverless handler
def handler(event):
    """Vercel serverless function handler"""
    try:
        # Convert Vercel event to Flask WSGI format
        method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        headers = event.get('headers', {})
        query_string = event.get('queryStringParameters', {})
        
        # Create WSGI environ
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'CONTENT_TYPE': headers.get('content-type', ''),
            'SERVER_NAME': 'vercel.app',
            'SERVER_PORT': '443',
            'wsgi.url_scheme': 'https',
            'QUERY_STRING': '&'.join([f"{k}={v}" for k, v in query_string.items()])
        }
        
        # Start response
        def start_response(status, headers):
            return {
                'statusCode': status,
                'headers': headers,
                'body': ''
            }
        
        # Get Flask response
        response = app(environ, start_response)
        
        # Extract response details
        status_code = response[0]
        response_headers = dict(response[1])
        response_body = response[2]
        
        # Return Vercel format
        return {
            'statusCode': status_code,
            'headers': response_headers,
            'body': response_body
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

# Export for Vercel
app.handler = handler
