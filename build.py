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
    
    # Create static dashboard HTML from the Flask app
    # Extract the dashboard HTML from annotcheck_desktop.py
    with open("annotcheck_desktop.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the DASHBOARD_HTML section
    start_marker = 'DASHBOARD_HTML = r"""'
    end_marker = '"""'
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Error: Could not find DASHBOARD_HTML in annotcheck_desktop.py")
        return
    
    start_idx += len(start_marker)
    end_idx = content.find(end_marker, start_idx)
    
    if end_idx == -1:
        print("Error: Could not find end of DASHBOARD_HTML")
        return
    
    dashboard_html = content[start_idx:end_idx]
    
    # Replace Flask-specific placeholders for static deployment
    dashboard_html = dashboard_html.replace('__DATA_MODE__', 'static')
    dashboard_html = dashboard_html.replace('__ADMIN_HASH__', 'static_admin_hash')
    
    # Add static data and modify JavaScript to work without Flask
    static_modifications = """
    <script>
    // Static data for demonstration
    var staticStudents = [
      "Deekshit K", "Aditi Deep", "Rajveer S", "Amresh R", "Neelambari V",
      "Deeksha K", "Varun Ravindran Nair", "Dipan K", "Charupriya", "Shivam C",
      "Shounak D", "Vaibhav V", "Avinash Verma", "Arkadeep", "Sarth Buch",
      "Aviral Yadav", "Pranjal M", "Mohith S", "Sudhesh S", "Anup Jeev",
      "Aaditya Goyal", "Pradyumn"
    ];
    
    var staticScores = {
      "Deekshit K": 90.7, "Aditi Deep": 89.8, "Rajveer S": 88.1, "Amresh R": 86.1,
      "Neelambari V": 85.8, "Deeksha K": 85.4, "Varun Ravindran Nair": 84.6,
      "Dipan K": 84.1, "Charupriya": 84.0, "Shivam C": 83.2, "Shounak D": 82.5,
      "Vaibhav V": 81.2, "Avinash Verma": 80.2, "Arkadeep": 78.8, "Sarth Buch": 76.5,
      "Aviral Yadav": 73.6, "Pranjal M": 72.7, "Mohith S": 62.5, "Sudhesh S": 60.4,
      "Anup Jeev": 56.0, "Aaditya Goyal": 0.0, "Pradyumn": 0.0
    };
    
    // Mock API functions for static deployment
    var M = {
      students: function() { return Promise.resolve(staticStudents); },
      scores: function() { 
        var scores = Object.keys(staticScores).map(name => ({Student: name, Overall_Score: staticScores[name]}));
        return Promise.resolve(scores);
      },
      perImageScores: function() { return Promise.resolve([]); },
      annotation: function(student, img) { return Promise.resolve({gt_boxes:[], student_boxes:[]}); },
      imgSrc: function(img) { return "https://via.placeholder.com/800x600/333/fff?text=Demo+Image+" + img; },
      images: function() { return Promise.resolve({images: staticStudents.map((s, i) => 'demo_' + i + '.jpg'), total: staticStudents.length}); }
    };
    
    // Override the boot function for static deployment
    function boot() {
      console.log('Static AnnotCheck Dashboard loaded');
      renderStudentList(staticStudents);
      document.getElementById('h-active').textContent = staticStudents.length + ' students';
      document.getElementById('sb-count').textContent = staticStudents.length;
      
      // Show demo content instead of real images
      document.getElementById('placeholder-msg').innerHTML = 
        '<div class="big">??</div><div>Static Demo Mode - Run locally for full functionality</div>';
    }
    
    // Start the application
    boot();
    </script>
    """
    
    # Insert the static modifications before the closing </body> tag
    dashboard_html = dashboard_html.replace('</body>', static_modifications + '</body>')
    
    index_html = dashboard_html
    
    with open(public_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    print("✅ Build completed successfully!")
    print(f"📁 Files copied to {public_dir.absolute()}")
    
if __name__ == "__main__":
    main()
