#!/usr/bin/env python3
"""
Vercel Build Script for AnnotCheck
Creates proper static deployment structure
"""

import os
import shutil
from pathlib import Path

def main():
    print("🔨 Starting Vercel build process...")
    
    # Create public directory
    public_dir = Path("public")
    public_dir.mkdir(exist_ok=True)
    
    # Copy main Python file to public directory
    shutil.copy("annotcheck_desktop.py", public_dir / "annotcheck_desktop.py")
    
    # Create API directory and copy serverless function
    api_dir = public_dir / "api"
    api_dir.mkdir(exist_ok=True)
    shutil.copy("api/index.py", api_dir / "index.py")
    
    # Copy requirements.txt for dependency installation
    shutil.copy("requirements.txt", public_dir / "requirements.txt")
    
    # Copy annotation project if it exists
    if Path("annotation_project").exists():
        shutil.copytree("annotation_project", public_dir / "annotation_project", dirs_exist_ok=True)
    
    # Create a simple index.html that redirects to the Python app
    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AnnotCheck - Loading...</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            margin: 0; 
            padding: 2rem; 
            text-align: center;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .loader { 
            width: 50px; 
            height: 50px; 
            border: 3px solid #f3f3f3; 
            border-top: 3px solid #3498db; 
            border-radius: 50%; 
            animation: spin 1s linear infinite; 
            margin-bottom: 1rem;
        }
        @keyframes spin { 
            0% { transform: rotate(0deg); } 
            100% { transform: rotate(360deg); } 
        }
        .message {
            font-size: 1.2rem;
            font-weight: 600;
            opacity: 0.9;
        }
        .error {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
            max-width: 500px;
        }
    </style>
</head>
<body>
    <div class="loader"></div>
    <div class="message">🚀 Starting AnnotCheck...</div>
    <div id="error-container"></div>
    
    <script>
        // Try to load the Python app
        fetch('/annotcheck_desktop.py')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to start application');
                }
                return response.text();
            })
            .then(html => {
                document.open();
                document.write(html);
                document.close();
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('error-container').innerHTML = 
                    '<div class="error">❌ Error starting application: ' + error.message + '</div>';
            });
    </script>
</body>
</html>"""
    
    with open(public_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    print("✅ Build completed successfully!")
    print(f"📁 Files copied to {public_dir.absolute()}")
    
if __name__ == "__main__":
    main()
