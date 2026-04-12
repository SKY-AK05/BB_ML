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
    
    # Create static dashboard HTML with real data
    # Check if static data exists
    static_data_dir = Path("static_data")
    if static_data_dir.exists() and (static_data_dir / "scores.json").exists():
        # Load real data
        import json
        with open(static_data_dir / "scores.json", "r") as f:
            real_data = json.load(f)
        
        # Extract real students and scores
        real_students = []
        real_scores = {}
        for item in real_data:
            student_name = item.get('student', 'Unknown')
            score = item.get('score', 0)
            real_students.append(student_name)
            real_scores[student_name] = score
        
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
        
        # Add real data and modify JavaScript to work without Flask
        real_data_script = f"""
    <script>
    // Real data from local processing
    var staticStudents = {json.dumps(real_students)};
    var staticScores = {json.dumps(real_scores)};
    
    // Mock API functions for static deployment
    var M = {{
      students: function() {{ return Promise.resolve(staticStudents); }},
      scores: function() {{ 
        var scores = Object.keys(staticScores).map(name => ({{Student: name, Overall_Score: staticScores[name]}}));
        return Promise.resolve(scores);
      }},
      perImageScores: function() {{ return Promise.resolve([]); }},
      annotation: function(student, img) {{ return Promise.resolve({{gt_boxes:[], student_boxes:[]}}); }},
      imgSrc: function(img) {{ return "https://via.placeholder.com/800x600/333/fff?text=Real+Data+" + img; }},
      images: function() {{ return Promise.resolve({{images: staticStudents.map((s, i) => 'real_' + i + '.jpg'), total: staticStudents.length}}); }}
    }};
    
    // Override the boot function for static deployment
    function boot() {{
      console.log('Static AnnotCheck Dashboard loaded with real data');
      renderStudentList(staticStudents);
      document.getElementById('h-active').textContent = staticStudents.length + ' students';
      document.getElementById('sb-count').textContent = staticStudents.length;
      
      // Show real data message
      document.getElementById('placeholder-msg').innerHTML = 
        '<div class="big">?</div><div>Real Data Mode - {len(real_students)} students processed</div>';
    }}
    
    // Start the application
    boot();
    </script>
    """
        
        # Insert the real data script before the closing </body> tag
        dashboard_html = dashboard_html.replace('</body>', real_data_script + '</body>')
        
        index_html = dashboard_html
        print(f"✅ Using real data from {len(real_students)} students")
    else:
        print("❌ No static data found. Please run annotcheck_desktop.py locally first.")
        # Fallback to demo HTML
        with open("public/index.html", "r", encoding="utf-8") as f:
            index_html = f.read()
    
    with open(public_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    print("✅ Build completed successfully!")
    print(f"📁 Files copied to {public_dir.absolute()}")
    
if __name__ == "__main__":
    main()
