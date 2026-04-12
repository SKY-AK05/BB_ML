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
    
    # Don't copy requirements.txt to prevent dependency installation
    
    # Copy annotation project if it exists
    if Path("annotation_project").exists():
        shutil.copytree("annotation_project", public_dir / "annotation_project", dirs_exist_ok=True)
    
    # Create static HTML version for Vercel deployment
    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AnnotCheck - Annotation Quality Assessment</title>
    <link href="https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@400;600;700;900&display=swap" rel="stylesheet"/>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
        :root{
          --mint:#b8f0d8;--yellow:#ffe033;--purple:#9b5de5;
          --cyan:#00e5c0;--red:#ff4757;--green:#3ddc97;
          --black:#111;--white:#fff;--gray:#f4f4f0;
          --border:2.5px solid #111;--radius:14px;
          --head:'Fredoka One',cursive;--body:'Nunito',sans-serif;
        }
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
        html,body{height:100%;font-family:var(--body);background:var(--mint);overflow:hidden;color:var(--black)}
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            text-align: center;
        }
        .title {
            font-family:var(--head);
            font-size: 3rem;
            color:var(--purple);
            margin-bottom: 1rem;
        }
        .subtitle {
            font-size: 1.2rem;
            color:var(--black);
            margin-bottom: 2rem;
        }
        .card {
            background:var(--white);
            border:var(--border);
            border-radius:var(--radius);
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 5px 5px 0 var(--black);
        }
        .card h3 {
            font-family:var(--head);
            color:var(--purple);
            margin-bottom: 1rem;
        }
        .btn {
            background:var(--purple);
            color:var(--white);
            border:var(--border);
            border-radius:8px;
            padding: 12px 24px;
            font-family:var(--head);
            font-size:16px;
            cursor:pointer;
            text-decoration:none;
            display:inline-block;
            margin: 0.5rem;
            transition:transform 0.1s;
        }
        .btn:hover {
            transform:scale(1.05);
        }
        .btn:active {
            transform:scale(0.95);
        }
        .warning {
            background:var(--yellow);
            color:var(--black);
            padding: 1rem;
            border-radius:8px;
            margin: 1rem 0;
            border:2px solid var(--black);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="title">ANNOT<span style="color:var(--purple)">.</span>CHECK</h1>
        <p class="subtitle">Annotation Quality Assessment Tool</p>
        
        <div class="card">
            <h3>?? Static Deployment Mode</h3>
            <p>This is a static version of AnnotCheck deployed on Vercel.</p>
            <p>The full dashboard with student analysis requires a local server environment.</p>
            
            <div class="warning">
                <strong>?? Note:</strong> For the complete interactive dashboard with real-time feedback and scoring, please run the application locally using the Python script.
            </div>
            
            <h3>?? Features Available:</h3>
            <ul style="text-align: left; max-width: 600px; margin: 0 auto;">
                <li>?? Comprehensive annotation rules and guidelines</li>
                <li>?? Personalized feedback system design</li>
                <li>?? Student performance analysis framework</li>
                <li>?? No-numbers motivational feedback approach</li>
            </ul>
            
            <h3>?? To Run Full Version Locally:</h3>
            <div style="background: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <code style="display: block; text-align: left; background: #fff; padding: 1rem; border-radius: 4px;">
                    git clone https://github.com/SKY-AK05/BB_ML.git<br>
                    cd annotcheck_deploy<br>
                    python annotcheck_desktop.py
                </code>
            </div>
            
            <div style="margin-top: 2rem;">
                <a href="https://github.com/SKY-AK05/BB_ML" class="btn">?? View on GitHub</a>
                <a href="mailto:your-email@example.com" class="btn">?? Contact Support</a>
            </div>
        </div>
        
        <div class="card">
            <h3>?? Recent Updates</h3>
            <ul style="text-align: left; max-width: 600px; margin: 0 auto;">
                <li>?? Implemented comprehensive no-numbers feedback system</li>
                <li>?? Added personalized student performance analysis</li>
                <li>?? Updated annotation rules with 80% confidence requirement</li>
                <li>?? Enhanced UI with encouraging, actionable guidance</li>
                <li>?? Fixed Vercel deployment configuration</li>
            </ul>
        </div>
    </div>
</body>
</html>"""
    
    with open(public_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    print("✅ Build completed successfully!")
    print(f"📁 Files copied to {public_dir.absolute()}")
    
if __name__ == "__main__":
    main()
