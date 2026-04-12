#!/usr/bin/env python3
"""
Vercel Serverless Function for AnnotCheck API
Handles Flask app deployment on Vercel
"""

import sys
import os
from pathlib import Path

# Add the parent directory to Python path so we can import our main app
sys.path.append(str(Path(__file__).parent.parent))

# Import the main Flask app
from annotcheck_desktop import app

# Vercel serverless handler
def handler(request):
    """Vercel serverless function handler"""
    return app(request.environ, lambda status_code, headers: (status_code, headers))

# Export for Vercel
app.handler = handler
