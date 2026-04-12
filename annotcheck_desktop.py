#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AnnotCheck Desktop - Annotation Quality Assessment Tool

A desktop application for evaluating student annotations against ground truth.
Originally converted from Google Colab notebook.

Features:
- Extract and organize student ZIP files and ground truth
- Score annotations using IoU, precision, recall, F1
- Interactive dashboard with analytics
- Local file processing (no cloud dependencies)

Usage:
    python annotcheck_desktop.py
"""

import os
import sys
import glob
import zipfile
import shutil
import threading
import hashlib
import json
from pathlib import Path

# Data processing
import pandas as pd
import xml.etree.ElementTree as ET

# Web dashboard
from flask import Flask, jsonify, send_file, request, abort, Response
from PIL import Image, ImageOps
import io

# Configuration
BASE_DIR = Path(__file__).parent / "annotation_project"
XML_DIR = BASE_DIR / "XML"
GT_DIR = BASE_DIR / "Ground_Truth"
IMG_DIR = BASE_DIR / "Images"
UPLOAD_DIR = Path(__file__).parent / "uploads"

# Create directories
for dir_path in [BASE_DIR, XML_DIR, GT_DIR, IMG_DIR, UPLOAD_DIR]:
    dir_path.mkdir(exist_ok=True)

# Flask app configuration
PAGE_SIZE = 24
ADMIN_PASSWORD = "orchvate2024"
ADMIN_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

def get_common_prefix(names):
    """Find the longest common prefix that ends at a word boundary"""
    if not names:
        return ""
    prefix = os.path.commonprefix(names)
    if not prefix:
        return ""
    # Walk back to the last word-boundary character
    for i in range(len(prefix) - 1, -1, -1):
        if prefix[i] in ("_", "-", " "):
            return prefix[:i + 1]
    return ""

def parse_cvat_xml(xml_path):
    """Parse a CVAT-for-Images 1.1 XML file"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result = {}
    
    for img_elem in root.findall("image"):
        img_name = os.path.basename(img_elem.get("name", ""))
        boxes = []
        for box in img_elem.findall("box"):
            label = box.get("label", "")
            xtl = float(box.get("xtl", 0))
            ytl = float(box.get("ytl", 0))
            xbr = float(box.get("xbr", 0))
            ybr = float(box.get("ybr", 0))
            boxes.append((label, xtl, ytl, xbr, ybr))
        result[img_name] = boxes
    
    return result

def iou(a, b):
    """Calculate Intersection-over-Union between two boxes"""
    xA = max(a[1], b[1]); yA = max(a[2], b[2])
    xB = min(a[3], b[3]); yB = min(a[4], b[4])
    inter = max(0.0, xB - xA) * max(0.0, yB - yA)
    area_a = (a[3] - a[1]) * (a[4] - a[2])
    area_b = (b[3] - b[1]) * (b[4] - b[2])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0

def _norm_stem(name):
    """Strip path and extension, lowercase. '1281.JPEG' -> '1281'"""
    return os.path.splitext(os.path.basename(name))[0].lower()

def lookup(d, name, img_stem_map=None):
    """Find annotation boxes for `name` inside dict `d`"""
    if name in d:
        return d[name]
    base = os.path.basename(name)
    if base in d:
        return d[base]
    
    # Extension-agnostic matching if stem map is provided
    if img_stem_map is not None:
        target = _norm_stem(name)
        for k in d:
            if _norm_stem(k) == target:
                return d[k]
    return []

def extract_zip_files():
    """Extract and organize ZIP files"""
    print_section("PART 1 - EXTRACTOR")
    
    # Check for existing ZIP files
    existing_zips = list(UPLOAD_DIR.glob("*.zip"))
    
    if existing_zips:
        print(f"Found {len(existing_zips)} ZIP file(s):")
        for z in existing_zips:
            print(f"   {z.name}")
        
        choice = input("\nUse existing files? (y/n): ").strip().lower()
    else:
        print("No ZIP files found in uploads directory.")
        print("Please place your ZIP files in the 'uploads' directory and run again.")
        return False
    
    if choice != "y":
        print("Please add your ZIP files to the 'uploads' directory and restart.")
        return False
    
    # Extract and organize
    gt_zip = None
    std_zips = []
    
    # Identify Ground Truth zip vs student zips
    for zip_path in existing_zips:
        fname = zip_path.name.lower()
        if "ground" in fname or "gt" in fname or "truth" in fname:
            gt_zip = zip_path
        else:
            std_zips.append(zip_path)
    
    if gt_zip is None:
        print("ERROR: Could not identify the Ground Truth ZIP.")
        print("Make sure its filename contains 'ground', 'gt', or 'truth'.")
        return False
    
    print(f"Ground Truth ZIP: {gt_zip.name}")
    print(f"Student ZIPs: {len(std_zips)} file(s)")
    
    # Detect and strip common prefix
    raw_student_names = [os.path.splitext(z.name)[0].strip() for z in std_zips]
    common_prefix = get_common_prefix(raw_student_names)
    
    if common_prefix:
        print(f"Detected common prefix: '{common_prefix}' - will be stripped from student names")
    else:
        print("No common prefix detected - names kept as-is")
    
    def strip_prefix(name):
        if common_prefix and name.startswith(common_prefix):
            return name[len(common_prefix):]
        return name
    
    # Extract Ground Truth
    print("\nExtracting Ground Truth...")
    tmp_gt = BASE_DIR / "tmp_gt"
    tmp_gt.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(gt_zip, "r") as z:
        z.extractall(tmp_gt)
    
    gt_count = 0
    for root, _, files in os.walk(tmp_gt):
        for f in files:
            if f.endswith(".xml"):
                shutil.copy(
                    os.path.join(root, f),
                    GT_DIR / f
                )
                gt_count += 1
    
    shutil.rmtree(tmp_gt, ignore_errors=True)
    print(f"GT XMLs saved to {GT_DIR} ({gt_count} file(s))")
    
    # Extract students
    print("\nExtracting student ZIPs...")
    image_exts = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
    extracted_imgs = 0
    students_ok = 0
    
    for zip_path in std_zips:
        raw_name = os.path.splitext(zip_path.name)[0].strip()
        student_name = strip_prefix(raw_name)
        tmp_dir = BASE_DIR / f"tmp_{raw_name}"
        tmp_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmp_dir)
        except zipfile.BadZipFile:
            print(f"WARNING: {zip_path.name} - bad ZIP, skipping.")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            continue
        
        xml_found = False
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                src = os.path.join(root, f)
                
                if f.endswith(".xml") and not xml_found:
                    dst = XML_DIR / f"{student_name}.xml"
                    shutil.copy(src, dst)
                    xml_found = True
                
                elif f.lower().endswith(image_exts):
                    dst = IMG_DIR / f
                    if not dst.exists():
                        shutil.copy(src, dst)
                        extracted_imgs += 1
        
        if xml_found:
            if raw_name != student_name:
                print(f"  {raw_name} -> {student_name}")
            else:
                print(f"  {student_name}")
            students_ok += 1
        else:
            print(f"WARNING: No XML found in {zip_path.name}")
        
        shutil.rmtree(tmp_dir, ignore_errors=True)
    
    # Summary
    print_section("Extraction complete!")
    print(f"Common prefix stripped: '{common_prefix or 'none'}'")
    print(f"Student XMLs: {len(list(XML_DIR.glob('*.xml')))}")
    print(f"GT XMLs: {len(list(GT_DIR.glob('*.xml')))}")
    print(f"Images: {len(list(IMG_DIR.glob('*')))}")
    
    return True

def score_annotations():
    """Score student annotations against ground truth"""
    print_section("PART 2 - SCORER")
    
    # Load ground truth
    gt_annotations = {}
    gt_files = list(GT_DIR.glob("*.xml"))
    
    if not gt_files:
        print(f"ERROR: No Ground Truth XMLs found in {GT_DIR}")
        return False
    
    for gtf in gt_files:
        gt_annotations.update(parse_cvat_xml(gtf))
    
    print(f"Ground Truth loaded: {len(gt_annotations)} image(s)")
    
    # Get student files
    student_files = sorted([f for f in XML_DIR.glob("*.xml")])
    
    if not student_files:
        print(f"ERROR: No student XMLs found in {XML_DIR}")
        return False
    
    print(f"Scoring {len(student_files)} student(s)...")
    
    # Scoring configuration
    IOU_THRESHOLD = 0.5
    
    summary_rows = []
    per_image_rows = []
    
    total_students = len(student_files)
    
    for idx, xml_file in enumerate(student_files, 1):
        student = xml_file.stem
        s_annots = parse_cvat_xml(xml_file)
        
        total_tp = total_fp = total_fn = 0
        iou_sum = 0.0
        matched = 0
        label_ok = 0
        
        for img_name, gt_boxes in gt_annotations.items():
            s_boxes = s_annots.get(img_name, [])
            used_gt = set()
            img_tp = 0
            img_iou = 0.0
            
            # Greedy best-IoU matching
            for sb in s_boxes:
                best, best_gi = 0.0, -1
                for gi, gb in enumerate(gt_boxes):
                    if gi in used_gt:
                        continue
                    score = iou(sb, gb)
                    if score > best:
                        best, best_gi = score, gi
                
                if best >= IOU_THRESHOLD and best_gi >= 0:
                    used_gt.add(best_gi)
                    img_tp += 1
                    img_iou += best
                    matched += 1
                    if sb[0] == gt_boxes[best_gi][0]:
                        label_ok += 1
            
            fp = len(s_boxes) - img_tp
            fn = len(gt_boxes) - img_tp
            
            total_tp += img_tp
            total_fp += fp
            total_fn += fn
            iou_sum += img_iou
            
            img_avg_iou = img_iou / max(img_tp, 1)
            
            per_image_rows.append({
                "Student": student,
                "Image": img_name,
                "GT_Boxes": len(gt_boxes),
                "S_Boxes": len(s_boxes),
                "TP": img_tp,
                "FP": fp,
                "FN": fn,
                "Avg_IoU": round(img_avg_iou, 4),
            })
        
        # Per-student aggregates
        prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
        rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        avg_io = iou_sum / matched if matched else 0.0
        lab_ac = label_ok / matched if matched else 0.0
        
        overall = (0.5 * f1) + (0.3 * avg_io) + (0.2 * lab_ac)
        fp_penalty = total_fp / (total_tp + total_fp + 1)
        overall = overall * (1 - 0.2 * fp_penalty)
        
        summary_rows.append({
            "Student": student,
            "Total_GT_Boxes": sum(len(v) for v in gt_annotations.values()),
            "TP": total_tp,
            "FP": total_fp,
            "FN": total_fn,
            "Avg_IoU": round(avg_io, 4),
            "Label_Accuracy": round(lab_ac * 100, 2),
            "Precision": round(prec * 100, 2),
            "Recall": round(rec * 100, 2),
            "F1_Score": round(f1 * 100, 2),
            "Overall_Score": round(overall * 100, 2),
        })
        
        bar = " " * idx + " " * (total_students - idx)
        pct = round(idx / total_students * 100)
        print(f"\r  [{bar}] {pct:3d}%  {student:<30}", end="", flush=True)
    
    print()
    
    # Save CSVs
    df_summary = pd.DataFrame(summary_rows).sort_values(
        "Overall_Score", ascending=False
    ).reset_index(drop=True)
    
    df_per_image = pd.DataFrame(per_image_rows)
    
    df_summary.to_csv(BASE_DIR / "scores.csv", index=False)
    df_per_image.to_csv(BASE_DIR / "per_image_scores.csv", index=False)
    
    # Print results
    print_section("SCORING RESULTS")
    print(
        df_summary[[
            "Student", "TP", "FP", "FN",
            "Avg_IoU", "Label_Accuracy", "Precision", "Recall", "Overall_Score",
        ]].to_string(index=False)
    )
    
    print(f"\nscores.csv -> {BASE_DIR / 'scores.csv'}")
    print(f"per_image_scores.csv -> {BASE_DIR / 'per_image_scores.csv'}")
    
    return True

# Load data for Flask app
def load_dashboard_data():
    """Load data for the Flask dashboard"""
    global gt_annotations, all_student_annots, image_list, _img_stem_map
    
    print_section("PART 3 - DASHBOARD")
    
    # Load ground truth annotations
    gt_annotations = {}
    for f in GT_DIR.glob("*.xml"):
        gt_annotations.update(parse_cvat_xml(f))
    
    # Load student annotations
    all_student_annots = {}
    for f in sorted(XML_DIR.glob("*.xml")):
        student_name = f.stem
        all_student_annots[student_name] = parse_cvat_xml(f)
    
    # Build image stem map for extension-agnostic matching
    _img_stem_map = {_norm_stem(f): f for f in os.listdir(IMG_DIR)}
    
    image_list = sorted(os.listdir(IMG_DIR))
    
    print(f"Loaded: {len(all_student_annots)} students | {len(gt_annotations)} GT images | {len(image_list)} images")
    
    # Quick sanity check
    gt_covered = sum(1 for img in image_list if lookup(gt_annotations, img, _img_stem_map))
    print(f"GT coverage: {gt_covered}/{len(image_list)} images have GT boxes")
    
    if gt_covered == 0:
        print("WARNING: NO GT BOXES FOUND - check image name matching!")
        print("GT XML sample keys:", list(gt_annotations.keys())[:3])
        print("Image list sample:", image_list[:3])

# Complete dashboard HTML from original notebook
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AnnotCheck</title>
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

#topnav{
  height:56px;background:var(--yellow);border-bottom:var(--border);
  display:flex;align-items:center;gap:8px;padding:0 14px;z-index:20;flex-shrink:0;
}
.logo{font-family:var(--head);font-size:20px;letter-spacing:1px;margin-right:6px;
  white-space:nowrap;cursor:default;user-select:none;}
.logo span{color:var(--purple)}
.nav-btn{
  height:34px;min-width:34px;padding:0 8px;border:var(--border);border-radius:8px;
  background:var(--white);cursor:pointer;font-size:13px;font-weight:900;
  display:flex;align-items:center;justify-content:center;gap:4px;
  transition:background .1s,transform .1s;user-select:none;white-space:nowrap;font-family:var(--body);
}
.nav-btn:hover{background:var(--mint)}
.nav-btn:active{transform:scale(.93)}
.nav-btn.active{background:var(--purple);color:var(--white);border-color:var(--purple)}
#img-counter{background:var(--white);border:var(--border);border-radius:8px;
  padding:4px 12px;font-family:var(--head);font-size:14px;min-width:80px;text-align:center;}
.hpill{background:var(--purple);color:var(--white);border:var(--border);
  border-radius:20px;padding:3px 12px;font-size:11px;font-weight:700;white-space:nowrap;}
.hpill.cyan{background:var(--cyan);color:var(--black)}
.hpill.admin-pill{background:#ff4757;color:var(--white);cursor:pointer;transition:background .15s}
.hpill.admin-pill:hover{background:#cc2233}
#stat-pills{display:flex;gap:5px}
.stat-pill{font-family:var(--head);font-size:11px;border:2px solid var(--black);
  border-radius:20px;padding:2px 9px;white-space:nowrap;}
#nav-spacer{flex:1}

#layout{display:grid;grid-template-columns:220px 1fr 300px;height:calc(100vh - 56px)}

#sidebar{background:var(--white);border-right:var(--border);display:flex;flex-direction:column;overflow:hidden}
#rules-sidebar{background:var(--white);border-left:var(--border);display:flex;flex-direction:column;overflow:hidden}
#rules-sidebar .sb-head{background:var(--cyan);color:var(--black);}
.sb-head{background:var(--purple);color:var(--white);font-family:var(--head);font-size:14px;
  padding:9px 14px;border-bottom:var(--border);flex-shrink:0;
  display:flex;align-items:center;justify-content:space-between;}
#sb-search{margin:8px;border:2px solid #ddd;border-radius:8px;padding:5px 10px;
  font-size:12px;font-family:var(--body);outline:none;flex-shrink:0;}
#sb-search:focus{border-color:var(--purple)}
#student-list{flex:1;overflow-y:auto;padding:6px;display:flex;flex-direction:column;gap:5px}
#student-list::-webkit-scrollbar{width:3px}
#student-list::-webkit-scrollbar-thumb{background:#ccc;border-radius:2px}
.student-card{border:2px solid var(--black);border-radius:10px;padding:7px 10px;cursor:pointer;
  display:flex;align-items:center;gap:8px;transition:transform .12s,box-shadow .12s;background:var(--white);}
.student-card:hover{transform:translateX(3px);box-shadow:-3px 3px 0 var(--black)}
.student-card.active{background:var(--yellow);box-shadow:-3px 3px 0 var(--black);transform:translateX(3px)}
.s-avatar{width:30px;height:30px;border-radius:7px;border:2px solid var(--black);
  display:flex;align-items:center;justify-content:center;font-family:var(--head);font-size:11px;
  flex-shrink:0;text-transform:uppercase;}
.s-name{font-weight:700;font-size:11px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;flex:1}
.s-score{font-family:var(--head);font-size:12px;background:var(--black);color:var(--yellow);border-radius:5px;padding:1px 6px;flex-shrink:0}

#main{display:flex;flex-direction:column;overflow:hidden}

#panel-review{display:flex;flex-direction:column;height:100%;overflow:hidden}
#canvas-wrap{flex:1;overflow:hidden;position:relative;background:#d4edda;cursor:grab}
#canvas-wrap.dragging{cursor:grabbing}
#zoom-stage{position:absolute;top:0;left:0;transform-origin:0 0;will-change:transform}
#viewer-canvas{display:block;border:var(--border);border-radius:var(--radius);background:#000;box-shadow:5px 5px 0 var(--black)}
#placeholder-msg{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:10px;font-family:var(--head);font-size:20px;color:#888;pointer-events:none;}
#placeholder-msg .big{font-size:46px}
#zoom-hint{position:absolute;bottom:10px;right:12px;background:rgba(0,0,0,.55);color:#fff;
  border-radius:20px;padding:3px 11px;font-size:11px;font-weight:700;
  pointer-events:none;transition:opacity .3s;opacity:0;}
#zoom-hint.show{opacity:1}
#zoom-controls{position:absolute;top:10px;right:12px;display:flex;flex-direction:column;gap:4px;z-index:5}
.zoom-ctrl-btn{width:28px;height:28px;border:var(--border);border-radius:7px;background:var(--white);
  cursor:pointer;font-size:15px;font-weight:900;display:flex;align-items:center;justify-content:center;
  transition:background .1s,transform .1s;user-select:none;box-shadow:2px 2px 0 var(--black);}
.zoom-ctrl-btn:hover{background:var(--yellow)}
.zoom-ctrl-btn:active{transform:scale(.9)}

/* ── annotation count badge ── */
#annot-badge{
  position:absolute;top:10px;left:12px;z-index:5;
  display:none;gap:5px;flex-direction:column;
}
.abadge{
  font-family:var(--head);font-size:11px;border:2px solid #111;
  border-radius:20px;padding:2px 10px;pointer-events:none;
}

#legend-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:7px 12px;background:var(--white);border-top:var(--border);
  font-size:12px;font-weight:700;flex-shrink:0;}
.toggle-btn{display:flex;align-items:center;gap:5px;border:2px solid var(--black);border-radius:20px;
  padding:3px 11px;cursor:pointer;font-weight:700;font-size:11px;
  font-family:var(--body);transition:all .15s;user-select:none;}
.toggle-btn .dot{width:11px;height:11px;border-radius:3px;border:2px solid var(--black);flex-shrink:0}
.toggle-btn.off{opacity:.4;text-decoration:line-through}
#toggle-gt{background:#d0faf2}
#toggle-gt:hover{background:#a0f0e0}
#toggle-std{background:#ffe0e3}
#toggle-std:hover{background:#ffc0c8}
#img-name-label{margin-left:auto;font-family:var(--head);font-size:12px;background:var(--mint);
  border:2px solid var(--black);border-radius:20px;padding:2px 11px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;}

#panel-scores{display:none;flex-direction:column;height:100%;overflow:hidden}
#scores-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:9px 14px;background:var(--yellow);border-bottom:var(--border);flex-shrink:0;}
.tb-label{font-family:var(--head);font-size:14px;margin-right:4px}
#score-view-select{border:2px solid #111;border-radius:8px;padding:4px 10px;
  font-family:var(--body);font-size:12px;font-weight:700;background:var(--white);cursor:pointer;outline:none;}
#score-search{border:2px solid #111;border-radius:8px;padding:4px 10px;font-size:12px;font-family:var(--body);outline:none;width:150px}
#score-search:focus{border-color:var(--purple)}
#score-row-count{margin-left:auto;font-family:var(--head);font-size:12px;color:#555}
#score-kpi-row{display:flex;gap:10px;padding:10px 14px;background:var(--white);
  border-bottom:var(--border);flex-shrink:0;overflow-x:auto;}
.kpi-card{flex-shrink:0;border:2px solid #111;border-radius:10px;padding:8px 14px;
  background:var(--gray);min-width:110px;display:flex;flex-direction:column;gap:2px;}
.kpi-label{font-size:10px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.5px}
.kpi-value{font-family:var(--head);font-size:20px}
#score-table-wrap{flex:1;overflow:auto}
#score-table-wrap table{width:100%;border-collapse:collapse;font-size:12px}
#score-table-wrap thead th{position:sticky;top:0;background:var(--purple);color:var(--white);
  font-family:var(--head);font-size:12px;padding:8px 11px;text-align:left;
  border:1px solid #111;white-space:nowrap;z-index:2;cursor:pointer;}
#score-table-wrap thead th.num{text-align:right}
#score-table-wrap thead th:hover{background:#7a3db5}
#score-table-wrap thead th[title]{text-decoration:underline dotted rgba(255,255,255,.5);text-underline-offset:3px}
#score-table-wrap tbody tr:nth-child(even){background:rgba(0,0,0,.035)}
#score-table-wrap tbody tr:hover{background:#fff8cc}
#score-table-wrap tbody td{padding:6px 11px;border:1px solid #e0e0e0;vertical-align:middle;white-space:nowrap}
#score-table-wrap tbody td.num{text-align:right;font-family:var(--head)}
.score-bar-wrap{display:flex;align-items:center;gap:7px;min-width:110px}
.score-bar{height:9px;border-radius:5px;border:1.5px solid #111;transition:width .3s}
.rank-badge{display:inline-flex;align-items:center;justify-content:center;
  width:22px;height:22px;border-radius:6px;border:2px solid #111;
  font-family:var(--head);font-size:11px;background:var(--mint);}
.rank-badge.gold{background:var(--yellow)}.rank-badge.silver{background:#e0e0e0}.rank-badge.bronze{background:#f4b57a}
#score-table-wrap::-webkit-scrollbar{width:5px;height:5px}
#score-table-wrap::-webkit-scrollbar-thumb{background:#bbb;border-radius:3px}

/* Analytics */
#panel-analytics{display:none;flex-direction:column;height:100%;overflow-y:auto;background:var(--gray)}
#panel-analytics::-webkit-scrollbar{width:5px}
#panel-analytics::-webkit-scrollbar-thumb{background:#bbb;border-radius:3px}
.analytics-header{background:var(--purple);color:var(--white);border-bottom:var(--border);
  padding:10px 16px;flex-shrink:0;display:flex;align-items:center;gap:10px;}
.analytics-header-title{font-family:var(--head);font-size:16px}
.analytics-header-sub{font-size:11px;opacity:.75}
.analytics-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;padding:14px;}
.chart-card{background:var(--white);border:var(--border);border-radius:var(--radius);padding:16px;box-shadow:4px 4px 0 var(--black);}
.chart-card.full-width{grid-column:1/-1}
.chart-title{font-family:var(--head);font-size:15px;margin-bottom:3px;display:flex;align-items:center;gap:7px;}
.chart-sub{font-size:11px;color:#777;margin-bottom:12px;font-style:italic}
.chart-inner{position:relative;height:240px}
.chart-card.full-width .chart-inner{height:260px}
.chart-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#aaa;font-size:13px;font-weight:700;}
.insight-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.insight-badge{font-size:11px;font-weight:700;border:2px solid #111;border-radius:20px;
  padding:3px 11px;display:flex;align-items:center;gap:5px;}
.insight-badge.green{background:#d4fde8}.insight-badge.red{background:#ffe0e3}
.insight-badge.yellow{background:var(--yellow)}.insight-badge.purple{background:#ede0ff}

#pw-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);
  z-index:1000;align-items:center;justify-content:center;}
#pw-overlay.show{display:flex}
#pw-card{background:var(--white);border:var(--border);border-radius:var(--radius);
  padding:30px 36px;display:flex;flex-direction:column;gap:16px;
  box-shadow:7px 7px 0 var(--black);min-width:320px;}
#pw-title{font-family:var(--head);font-size:24px;text-align:center}
#pw-sub{font-size:12px;color:#888;text-align:center;margin-top:-8px}
#pw-input{border:var(--border);border-radius:10px;padding:11px 16px;font-size:15px;font-family:var(--body);outline:none;}
#pw-input:focus{border-color:var(--purple)}
#pw-error{color:var(--red);font-size:12px;font-weight:700;min-height:18px;text-align:center}
#pw-btns{display:flex;gap:10px;justify-content:flex-end}
.pw-btn{padding:9px 22px;border:var(--border);border-radius:9px;font-family:var(--head);font-size:14px;cursor:pointer;transition:background .12s,transform .1s;}
.pw-btn:active{transform:scale(.95)}
.pw-btn.cancel{background:var(--gray)}.pw-btn.cancel:hover{background:#dedede}
.pw-btn.unlock{background:var(--purple);color:var(--white)}.pw-btn.unlock:hover{background:#7a40c4}
</style>
</head>
<body>

<nav id="topnav">
  <div class="logo" id="logo-trigger">ANNOT<span>.</span>CHECK</div>
  <div id="nav-img-controls" style="display:flex;align-items:center;gap:6px;">
    <button class="nav-btn" onclick="navImg(-999)"></button>
    <button class="nav-btn" onclick="navImg(-10)">«</button>
    <button class="nav-btn" onclick="navImg(-1)"></button>
    <div id="img-counter"> / </div>
    <button class="nav-btn" onclick="navImg(1)">></button>
    <button class="nav-btn" onclick="navImg(10)">»</button>
    <button class="nav-btn" onclick="navImg(999)"></button>
    <input id="img-search" type="number" placeholder="Go to image..." style="width:100px;border:2px solid #111;border-radius:6px;padding:4px 8px;font-size:12px;font-family:var(--body);outline:none;" onkeydown="if(event.key==='Enter')goToImage()" min="1"/>
  </div>
  <div id="stat-pills" style="margin-left:8px;"></div>
  <div id="nav-spacer"></div>
  <div id="admin-badge" class="hpill admin-pill" style="display:none;" onclick="promptLock()"> ADMIN</div>
  <div id="nav-tabs" style="display:flex;gap:5px;margin-left:8px;">
    <button id="tab-review"    class="nav-btn active"   onclick="switchTab('review')"> Review</button>
    <button id="tab-scores"    class="nav-btn" style="display:none" onclick="switchTab('scores')"> Scores</button>
    <button id="tab-analytics" class="nav-btn" style="display:none" onclick="switchTab('analytics')"> Analytics</button>
  </div>
  <div class="hpill"      id="h-active" style="margin-left:8px;">—</div>
  <div class="hpill cyan" id="h-total">0 imgs</div>
</nav>

<div id="pw-overlay">
  <div id="pw-card">
    <div id="pw-title">🔑 Admin Access</div>
    <div id="pw-sub">Enter password to unlock scoring data</div>
    <input id="pw-input" type="password" placeholder="Password…" onkeydown="if(event.key==='Enter')submitPw()"/>
    <div id="pw-error"></div>
    <div id="pw-btns">
      <button class="pw-btn cancel" onclick="closePw()">Cancel</button>
      <button class="pw-btn unlock" onclick="submitPw()">Unlock</button>
    </div>
  </div>
</div>

<div id="layout">
  <aside id="sidebar">
    <div class="sb-head">
      <span>👥 Students</span>
      <span id="sb-count" style="font-size:11px;opacity:.8;"></span>
    </div>
    <input id="sb-search" type="text" placeholder="🔍 Search students…" oninput="filterStudents()"/>
    <div id="student-list"><div style="padding:20px;text-align:center;color:#bbb;font-size:13px;">Loading…</div></div>
  </aside>

  <main id="main">
    <!-- ══ REVIEW ══ -->
    <div id="panel-review">
      <div id="canvas-wrap">
        <div id="placeholder-msg">
          <div class="big">🖼️</div>
          <div>Pick a student, then click an image</div>
        </div>
        <div id="zoom-stage"><canvas id="viewer-canvas"></canvas></div>
        <!-- Annotation count badge (always visible when image is open) -->
        <div id="annot-badge">
          <div class="abadge" id="ab-gt"  style="background:#d0faf2">GT: —</div>
          <div class="abadge" id="ab-std" style="background:#ffe0e3">You: —</div>
        </div>
        <div id="zoom-controls">
          <button class="zoom-ctrl-btn" onclick="zoomBy(1.25)">+</button>
          <button class="zoom-ctrl-btn" onclick="resetZoom()">⊙</button>
          <button class="zoom-ctrl-btn" onclick="zoomBy(0.8)">−</button>
        </div>
        <div id="zoom-hint">100%</div>
      </div>
      <div id="legend-bar">
        <button id="toggle-gt"  class="toggle-btn" onclick="toggleLayer('gt')"><span class="dot" style="background:#00e5c0"></span> Ground Truth</button>
        <button id="toggle-std" class="toggle-btn" onclick="toggleLayer('std')"><span class="dot" style="background:#ff4757"></span> Student</button>
        <div id="img-name-label">—</div>
      </div>
    </div>

    <!-- ══ SCORES ══ -->
    <div id="panel-scores">
      <div id="scores-toolbar">
        <span class="tb-label">📊 Score Sheet</span>
        <select id="score-view-select" onchange="renderScoreView()">
          <option value="summary">Summary — per student</option>
          <option value="perimage">Per-image breakdown</option>
        </select>
        <input id="score-search" type="text" placeholder="🔍 Filter rows…" oninput="renderScoreView()"/>
        <button class="nav-btn" onclick="downloadCSV()">⬇ CSV</button>
        <span id="score-row-count"></span>
      </div>
      <div id="score-kpi-row" style="display:none;"></div>
      <div id="score-table-wrap"><div style="text-align:center;color:#bbb;padding:60px;font-size:14px;">Loading scores…</div></div>
    </div>

    <!-- ══ ANALYTICS ══ -->
    <div id="panel-analytics">
      <div class="analytics-header">
        <div>
          <div class="analytics-header-title">📈 Student Performance Analytics</div>
          <div class="analytics-header-sub">Visual breakdown — who's excelling, and where</div>
        </div>
      </div>
      <div class="analytics-grid" id="analytics-grid">
        <div class="chart-card full-width">
          <div class="chart-title">🏆 Overall Score Leaderboard</div>
          <div class="chart-sub">Ranked by weighted score combining F1, IoU, label accuracy and FP penalty</div>
          <div class="chart-inner"><canvas id="chart-leaderboard"></canvas><div class="chart-loading" id="load-leaderboard">Loading…</div></div>
          <div class="insight-row" id="insight-leaderboard"></div>
        </div>
        <div class="chart-card">
          <div class="chart-title">🎯 Precision vs Recall</div>
          <div class="chart-sub">X = Precision · Y = Recall · top-right is ideal</div>
          <div class="chart-inner"><canvas id="chart-pr-scatter"></canvas><div class="chart-loading" id="load-pr">Loading…</div></div>
          <div class="insight-row" id="insight-pr"></div>
        </div>
        <div class="chart-card">
          <div class="chart-title">📦 Average IoU per Student</div>
          <div class="chart-sub">Tightness of box overlap — higher is better</div>
          <div class="chart-inner"><canvas id="chart-iou"></canvas><div class="chart-loading" id="load-iou">Loading…</div></div>
          <div class="insight-row" id="insight-iou"></div>
        </div>
        <div class="chart-card">
          <div class="chart-title">🔍 Best Box Finders (Recall)</div>
          <div class="chart-sub">Who detects most objects without missing them</div>
          <div class="chart-inner"><canvas id="chart-recall"></canvas><div class="chart-loading" id="load-recall">Loading…</div></div>
          <div class="insight-row" id="insight-recall"></div>
        </div>
        <div class="chart-card">
          <div class="chart-title">✅ Most Precise Annotators</div>
          <div class="chart-sub">Who draws the cleanest, most correct boxes</div>
          <div class="chart-inner"><canvas id="chart-precision"></canvas><div class="chart-loading" id="load-precision">Loading…</div></div>
          <div class="insight-row" id="insight-precision"></div>
        </div>
        <div class="chart-card full-width">
          <div class="chart-title">🔢 Error Breakdown — TP / FP / FN per Student</div>
          <div class="chart-sub">Green = correct · Red = wrong boxes · Orange = missed</div>
          <div class="chart-inner"><canvas id="chart-errors"></canvas><div class="chart-loading" id="load-errors">Loading…</div></div>
        </div>
        <div class="chart-card full-width">
          <div class="chart-title">🕸️ Multi-Metric Radar — Top 5 Students</div>
          <div class="chart-sub">F1, Precision, Recall, IoU, Label Accuracy for top performers</div>
          <div class="chart-inner" style="height:320px"><canvas id="chart-radar"></canvas><div class="chart-loading" id="load-radar">Loading…</div></div>
        </div>
      </div>
    </div>
  </main>

  <!-- Rules & Feedback Sidebar -->
  <aside id="rules-sidebar">
    <div class="sb-head">
      <span>?? Rules & Tips</span>
    </div>
    
    <!-- Rules Section -->
    <div id="rules-section" style="padding:12px;overflow-y:auto;flex:1;">
      <h3 style="font-family:var(--head);font-size:14px;margin-bottom:8px;color:var(--purple);">Annotation Rules</h3>
      <div id="rules-content" style="font-size:11px;line-height:1.4;">
        <div style="background:#fff8e1;border:2px solid #ffc107;border-radius:8px;padding:9px 10px;margin-bottom:8px;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
            <span style="background:#ffc107;color:#111;font-size:9px;font-weight:900;border-radius:4px;padding:1px 6px;">RULE 1</span>
            <strong style="font-size:12px;">80% Confidence Required</strong>
          </div>
          <div style="color:#444;">Only annotate if you are <strong>at least 80% sure</strong> it is a license plate.</div>
          <div style="margin-top:5px;background:#fffde7;border-radius:5px;padding:5px 7px;color:#888;font-style:italic;">
            &#10060; Skip if you're unsure - a missed plate is better than a wrong annotation
          </div>
        </div>
        <div style="background:#e8f5e9;border:2px solid #4caf50;border-radius:8px;padding:9px 10px;margin-bottom:8px;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
            <span style="background:#4caf50;color:#fff;font-size:9px;font-weight:900;border-radius:4px;padding:1px 6px;">RULE 2</span>
            <strong style="font-size:12px;">50% Plate Must Be Visible</strong>
          </div>
          <div style="color:#444;">Annotate only if <strong>at least half the license plate</strong> is visible in the image.</div>
          <div style="margin-top:5px;background:#f1f8e9;border-radius:5px;padding:5px 7px;color:#888;font-style:italic;">
            &#10060; Skip heavily cropped or mostly hidden plates
          </div>
        </div>
        <div style="background:#e3f2fd;border:2px solid #2196f3;border-radius:8px;padding:9px 10px;margin-bottom:8px;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
            <span style="background:#2196f3;color:#fff;font-size:9px;font-weight:900;border-radius:4px;padding:1px 6px;">RULE 3</span>
            <strong style="font-size:12px;">All Edges Must Be Visible</strong>
          </div>
          <div style="color:#444;">All <strong>4 edges of the license plate</strong> must be clearly visible before annotating.</div>
          <div style="margin-top:5px;background:#e8f4fd;border-radius:5px;padding:5px 7px;color:#888;font-style:italic;">
            &#10060; Do not annotate if any edge goes outside the image frame
          </div>
        </div>
        <div style="background:#f3e5f5;border:2px solid #9b5de5;border-radius:8px;padding:9px 10px;margin-bottom:8px;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
            <span style="background:#9b5de5;color:#fff;font-size:9px;font-weight:900;border-radius:4px;padding:1px 6px;">RULE 4</span>
            <strong style="font-size:12px;">Tight Box - No Gaps</strong>
          </div>
          <div style="color:#444;">Draw the box <strong>as tight as possible</strong> around the plate edges - no extra space.</div>
          <div style="margin-top:5px;background:#fce4ec;border-radius:5px;padding:5px 7px;color:#888;font-style:italic;">
            &#10060; Avoid loose boxes with large gaps around the plate
          </div>
        </div>
        <div style="background:#111;border-radius:8px;padding:9px 11px;margin-top:4px;">
          <div style="color:#ffe033;font-family:var(--head);font-size:12px;margin-bottom:5px;">&#9889; Quick Checklist</div>
          <div style="color:#eee;font-size:11px;line-height:1.8;">
            &#9744;&nbsp; Am I 80%+ sure this is a license plate?<br>
            &#9744;&nbsp; Is 50% or more of the plate visible?<br>
            &#9744;&nbsp; Are all 4 edges clearly visible?<br>
            &#9744;&nbsp; Is my box as tight as possible?
          </div>
        </div>
      </div>
    </div>
    
    <!-- Feedback Section -->
    <div id="feedback-section" style="border-top:var(--border);padding:12px;overflow-y:auto;flex:1;">
      <h3 style="font-family:var(--head);font-size:14px;margin-bottom:8px;color:var(--cyan);">Personalized Feedback</h3>
      <div id="feedback-content" style="font-size:11px;line-height:1.4;">
        <div style="text-align:center;color:#999;padding:20px;">
          Select a student to see personalized feedback
        </div>
      </div>
    </div>
  </aside>
</div>

<script>
var DATA_MODE  = '__DATA_MODE__';
var ADMIN_HASH = '__ADMIN_HASH__';

var isAdmin=false, currentStudent=null;
var allImages=[], currentIdx=-1, totalImages=0, currentPage=0, totalPages=0;
var scoreMap={}, lastAnnot=null;
var showGT=true, showStd=true;
var summaryData=[], perImageData=[], scoresLoaded=false, analyticsLoaded=false;
var allStudents=[], sortCol=null, sortAsc=true;
var _manifest=null, _annotations=null, _chartInstances={};

var COL_TIPS = {
  'Student':'Student annotator name',
  'Overall Score':'Weighted composite: F1×0.4 + IoU×0.3 + Label Accuracy×0.2 − FP penalty×0.1',
  'F1 Score':'Harmonic mean of Precision and Recall — overall detection quality',
  'Precision':'Of all boxes drawn, what % were correct (low FP = high precision)',
  'Recall':'Of all actual objects, what % were found (low FN = high recall)',
  'Avg IoU':'Average overlap between student boxes and ground truth',
  'Label Accuracy':'Of matched boxes, what % had the correct class label',
  'TP':'True Positives — correctly matched boxes',
  'FP':'False Positives — extra/wrong boxes with no GT match',
  'FN':'False Negatives — GT objects the student missed',
  'GT Boxes':'Total ground-truth boxes across all images',
  'S Boxes':'Total boxes this student drew',
  'Total GT Boxes':'Ground-truth box count for this image',
  'Image':'Image filename',
};

// ── API abstraction ──────────────────────────────────────────
async function loadManifest(){if(!_manifest)_manifest=await safeJson('/data/manifest.json');return _manifest;}
async function loadAnnotations(){if(!_annotations)_annotations=await safeJson('/data/annotations.json');return _annotations;}

var M={
  async students(){
    if(DATA_MODE==='flask') return safeJson('/api/students');
    var m=await loadManifest(); return m?m.students:[];
  },
  async images(page){
    if(DATA_MODE==='flask') return safeJson('/api/images?page='+page);
    var m=await loadManifest(); var imgs=m?m.images:[];
    var PS=24, start=page*PS;
    return{images:imgs.slice(start,start+PS),total:imgs.length,page:page,pages:Math.ceil(imgs.length/PS)};
  },
  async annotation(student, imgName){
    if(DATA_MODE==='flask'){
      return safeJson('/api/annotation/'+encodeURIComponent(student)+'/'+encodeURIComponent(imgName));
    }
    var a=await loadAnnotations();
    var entry=(a&&a[imgName])?a[imgName]:{};
    var gt=entry.gt||[];
    var std=(entry.students&&entry.students[student])?entry.students[student]:[];
    return{gt_boxes:gt,student_boxes:std};
  },
  imgSrc(imgName){
    if(DATA_MODE==='flask') return '/api/image/'+encodeURIComponent(imgName);
    return '/images/'+encodeURIComponent(imgName.replace(/\.[^/.]+$/,'.jpg'));
  },
  async scores(){return safeJson(DATA_MODE==='flask'?'/api/scores':'/data/scores.json');},
  async perImageScores(){return safeJson(DATA_MODE==='flask'?'/api/per_image_scores':'/data/per_image_scores.json');},
};

async function safeJson(url){
  try{
    var r=await fetch(url);
    if(!r.ok){console.warn('[safeJson '+r.status+'] '+url);return null;}
    return JSON.parse(await r.text());
  }catch(e){console.error('[safeJson error]',url,e);return null;}
}

// ── Admin unlock ─────────────────────────────────────────────
var _lc=0,_lt=null;
document.getElementById('logo-trigger').addEventListener('click',function(){
  _lc++;clearTimeout(_lt);_lt=setTimeout(function(){_lc=0;},800);
  if(_lc>=3){_lc=0;if(!isAdmin)showPw();}
});
function showPw(){document.getElementById('pw-input').value='';document.getElementById('pw-error').textContent='';
  document.getElementById('pw-overlay').classList.add('show');
  setTimeout(function(){document.getElementById('pw-input').focus();},80);}
function closePw(){document.getElementById('pw-overlay').classList.remove('show');}
async function submitPw(){
  var hash=await sha256(document.getElementById('pw-input').value);
  if(hash===ADMIN_HASH){closePw();unlockAdmin();}
  else{document.getElementById('pw-error').textContent='❌ Wrong password';
    document.getElementById('pw-input').value='';document.getElementById('pw-input').focus();}
}
async function sha256(str){
  var buf=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(function(b){return b.toString(16).padStart(2,'0');}).join('');
}
function unlockAdmin(){
  isAdmin=true;
  document.getElementById('admin-badge').style.display='';
  document.getElementById('tab-scores').style.display='';
  document.getElementById('tab-analytics').style.display='';
  renderStudentList(allStudents);if(lastAnnot)updateStatPills(lastAnnot);
}
function promptLock(){
  if(confirm('Lock admin mode?')){
    isAdmin=false;
    document.getElementById('admin-badge').style.display='none';
    document.getElementById('tab-scores').style.display='none';
    document.getElementById('tab-analytics').style.display='none';
    switchTab('review');renderStudentList(allStudents);if(lastAnnot)updateStatPills(lastAnnot);
  }
}
document.getElementById('pw-overlay').addEventListener('click',function(e){if(e.target===this)closePw();});

// ── Zoom / Pan ───────────────────────────────────────────────
var scale=1,panX=0,panY=0,isPanning=false,startX=0,startY=0,startPanX=0,startPanY=0;
var stage=document.getElementById('zoom-stage'), wrap=document.getElementById('canvas-wrap');
function applyTransform(){stage.style.transform='translate('+panX+'px,'+panY+'px) scale('+scale+')';}
function centerCanvas(){var cv=document.getElementById('viewer-canvas'),wr=wrap.getBoundingClientRect();
  panX=(wr.width-cv.width*scale)/2;panY=(wr.height-cv.height*scale)/2;applyTransform();}
function resetZoom(){var cv=document.getElementById('viewer-canvas');if(!cv.width)return;
  var wr=wrap.getBoundingClientRect();
  scale=Math.min(wr.width/cv.width,wr.height/cv.height,1)*0.93;centerCanvas();showZoomHint();}
function zoomBy(f,cx,cy){var wr=wrap.getBoundingClientRect();
  cx=cx!=null?cx:wr.width/2;cy=cy!=null?cy:wr.height/2;
  var ns=Math.min(12,Math.max(0.15,scale*f)),r=ns/scale;
  panX=cx-r*(cx-panX);panY=cy-r*(cy-panY);scale=ns;applyTransform();showZoomHint();}
var _hTimer;
function showZoomHint(){var h=document.getElementById('zoom-hint');
  h.textContent=Math.round(scale*100)+'%';h.classList.add('show');
  clearTimeout(_hTimer);_hTimer=setTimeout(function(){h.classList.remove('show');},1400);}
wrap.addEventListener('wheel',function(e){e.preventDefault();var r=wrap.getBoundingClientRect();
  zoomBy(e.deltaY<0?1.1:0.9,e.clientX-r.left,e.clientY-r.top);},{passive:false});
wrap.addEventListener('mousedown',function(e){if(e.button!==0)return;
  isPanning=true;startX=e.clientX;startY=e.clientY;startPanX=panX;startPanY=panY;wrap.classList.add('dragging');});
window.addEventListener('mousemove',function(e){if(!isPanning)return;
  panX=startPanX+(e.clientX-startX);panY=startPanY+(e.clientY-startY);applyTransform();});
window.addEventListener('mouseup',function(){isPanning=false;wrap.classList.remove('dragging');});

// ── Tab switching ────────────────────────────────────────────
function switchTab(tab){
  var isR=(tab==='review'),isS=(tab==='scores'),isA=(tab==='analytics');
  document.getElementById('panel-review').style.display=isR?'flex':'none';
  document.getElementById('panel-scores').style.display=isS?'flex':'none';
  document.getElementById('panel-analytics').style.display=isA?'flex':'none';
  document.getElementById('tab-review').classList.toggle('active',isR);
  document.getElementById('tab-scores').classList.toggle('active',isS);
  document.getElementById('tab-analytics').classList.toggle('active',isA);
  document.getElementById('nav-img-controls').style.display=isR?'flex':'none';
  if(isS&&!scoresLoaded)loadScoreData();
  if(isA&&!analyticsLoaded)loadAnalyticsData();
}
function toggleLayer(w){
  if(w==='gt'){showGT=!showGT;document.getElementById('toggle-gt').classList.toggle('off',!showGT);}
  if(w==='std'){showStd=!showStd;document.getElementById('toggle-std').classList.toggle('off',!showStd);}
  if(lastAnnot)redraw(lastAnnot);
}

// ── Boot ─────────────────────────────────────────────────────
async function boot(){
  var results=await Promise.all([M.scores(),M.perImageScores()]);
  var sc=results[0];
  summaryData=sc||[]; // Load summary data for feedback system
  perImageData=results[1]||[];
  if(sc)sc.forEach(function(r){scoreMap[r.Student]=r.Overall_Score;});
  var sts=await M.students();
  if(sts){allStudents=sts;renderStudentList(allStudents);
    document.getElementById('h-active').textContent=allStudents.length+' students';
    document.getElementById('sb-count').textContent=allStudents.length;}
  await fetchMoreImages(false);
  
  // Auto-select first student and load first image
  if(allStudents.length > 0){
    await selectStudent(allStudents[0]);
    if(allImages.length > 0){
      await openImage(0);
    }
  }
}

function renderStudentList(list){
  var el=document.getElementById('student-list');el.innerHTML='';
  var colors=['#ffe033','#00e5c0','#ff6b9d','#9b5de5','#ff4757','#3ddc97','#ff922b'];
  list.forEach(function(name,i){
    var score=(isAdmin&&scoreMap[name]!=null)?scoreMap[name]:null;
    var initials=name.split(/[\s_\-]+/).map(function(w){return w[0]||'';}).join('').slice(0,2).toUpperCase();
    var card=document.createElement('div');
    card.className='student-card';card.dataset.name=name;
    card.innerHTML='<div class="s-avatar" style="background:'+colors[i%colors.length]+'">'+initials+'</div>'+
      '<span class="s-name">'+name+'</span>'+
      (score!=null?'<span class="s-score">'+score+'%</span>':'');
    card.addEventListener('click',function(){selectStudent(name);});
    el.appendChild(card);
  });
}

function filterStudents(){
  var q=document.getElementById('sb-search').value.toLowerCase();
  renderStudentList(q?allStudents.filter(function(n){return n.toLowerCase().indexOf(q)>=0;}):allStudents);
  if(currentStudent)document.querySelectorAll('.student-card').forEach(function(c){
    c.classList.toggle('active',c.dataset.name===currentStudent);});
}

function generateFeedback(data) {
  var FN = data.fn || 0;
  var FP = data.fp || 0;
  var iou = data.avg_iou || 0;
  var total = data.total_gt || 1;
  var missRate = FN / total;
  var fpRate   = FP / total;

  if(total === 0) return { type:'good', msg:'No plates expected in this image.', tip:'' };

  if(missRate > 0.15 && fpRate > 0.15)
    return { type:'warn', msg:'Some plates were missed and some boxes were in wrong areas.', tip:'Scan the full image carefully and only mark what you are confident about.' };
  if(missRate > 0.15)
    return { type:'warn', msg:'Not all license plates were found in this image.', tip:'Look at every corner of the image - plates can be small or partially hidden.' };
  if(fpRate > 0.15)
    return { type:'warn', msg:'Some boxes were placed on areas that are not license plates.', tip:'Only draw a box if you are confident it is a license plate.' };
  if(iou < 0.88 && iou > 0)
    return { type:'tip', msg:'Boxes could fit tighter around the plates.', tip:'Try to hug the edges of the plate as closely as possible.' };

  return { type:'good', msg:'All plates found and boxes look good!', tip:'Keep making boxes as tight as possible around the plate edges.' };
}

function generateOverallFeedback(student) {
  var row = summaryData.find(function(r){ return r.Student === student; });
  if(!row) return null;

  var overall   = parseFloat(row.Overall_Score) || 0;
  var precision = parseFloat(row.Precision)     || 0;
  var recall    = parseFloat(row.Recall)        || 0;
  var iou       = parseFloat(row.Avg_IoU)       || 0;
  var labelAcc  = parseFloat(row.Label_Accuracy)|| 0;
  var tp        = parseInt(row.TP)              || 0;

  var missingPlates = recall < 75;
  var tooManyWrong  = precision < 75;
  var looseBoxes    = iou < 0.88 && iou > 0;
  var labelIssues   = labelAcc < 90 && labelAcc > 0;
  var didNothing    = tp === 0;

  var tips = [];

  if(didNothing){
    tips.push({ icon:'&#128230;', text:'No annotations submitted.', tip:'Please open each image and annotate every license plate you can find.' });
  } else {
    if(missingPlates && tooManyWrong){
      tips.push({ icon:'&#128270;', text:'Focus on finding more license plates.', tip:'Scan the whole image slowly - plates can appear at different angles and sizes.' });
      tips.push({ icon:'&#127919;', text:'Be more careful about what you mark.', tip:'Only draw a box when you are at least 80% sure it is a license plate.' });
    } else if(missingPlates){
      tips.push({ icon:'&#128270;', text:'Focus on finding more license plates.', tip:'Scan the full image carefully - check every vehicle, corner, and background area.' });
    } else if(tooManyWrong){
      tips.push({ icon:'&#127919;', text:'Reduce wrong annotations.', tip:'You are marking areas that are not license plates. Apply the 80% confidence rule before drawing a box.' });
    }
    if(looseBoxes){
      tips.push({ icon:'&#128230;', text:'Make your boxes tighter.', tip:'Box edges should touch the plate edges as closely as possible - remove gaps on all sides.' });
    }
    if(labelIssues){
      tips.push({ icon:'&#127991;', text:'Double-check labels before saving.', tip:'Some boxes have the wrong label type. Re-read the label guide if you are unsure.' });
    }
  }

  var verdict, verdictColor, verdictBorder;
  if(didNothing){
    verdict = '&#128230; No work submitted yet.';
    verdictColor = '#F1EFE8'; verdictBorder = '#B4B2A9';
  } else if(overall >= 85){
    verdict = '&#127775; Great work - keep this up!';
    verdictColor = '#EAF3DE'; verdictBorder = '#639922';
  } else if(overall >= 70){
    verdict = '&#9989; Good progress - a few things to tighten up.';
    verdictColor = '#FAEEDA'; verdictBorder = '#BA7517';
  } else if(overall >= 50){
    verdict = '&#128200; You are improving - focus on the tips below.';
    verdictColor = '#FAECE7'; verdictBorder = '#993C1D';
  } else {
    verdict = '&#128170; Keep going - review the rules carefully.';
    verdictColor = '#FBEAF0'; verdictBorder = '#993556';
  }

  return { verdict:verdict, verdictColor:verdictColor, verdictBorder:verdictBorder, tips:tips };
}

function updateFeedback(studentName, imageData) {
  var feedbackDiv = document.getElementById('feedback-content');
  var html = '';

  // ?? Overall section ??
  var ov = generateOverallFeedback(studentName);
  if(ov){
    html += '<div style="padding:10px 12px 4px;">';
    html += '<div style="font-family:var(--head);font-size:13px;color:var(--purple);margin-bottom:8px;">&#128200; Overall Feedback</div>';

    // Verdict banner - no numbers
    html += '<div style="background:'+ov.verdictColor+';border-radius:8px;padding:10px 12px;margin-bottom:8px;border:2px solid '+ov.verdictBorder+';">';
    html += '<div style="font-size:13px;font-weight:700;">'+ov.verdict+'</div>';
    html += '</div>';

    if(ov.tips.length > 0){
      html += '<div style="font-size:11px;font-weight:700;color:#555;margin-bottom:6px;">Areas to improve:</div>';
      ov.tips.forEach(function(t){
        html += '<div style="background:#fffbf0;border-left:3px solid #ff9800;border-radius:0 6px 6px 0;padding:8px 10px;margin-bottom:6px;">';
        html += '<div style="font-size:12px;font-weight:700;">'+t.icon+' '+t.text+'</div>';
        html += '<div style="font-size:11px;color:#666;margin-top:3px;">&#128073; '+t.tip+'</div>';
        html += '</div>';
      });
    } else {
      html += '<div style="background:#e8f5e8;border-left:3px solid #4caf50;border-radius:0 6px 6px 0;padding:8px 10px;font-size:12px;font-weight:700;">&#9989; No issues found - excellent consistency!</div>';
    }
    html += '</div>';
    html += '<div style="border-top:2px dashed #ddd;margin:6px 0;"></div>';
  }

  // ?? Per-image section ??
  html += '<div style="padding:0 12px 10px;">';
  html += '<div style="font-family:var(--head);font-size:13px;color:var(--cyan);margin-bottom:8px;">&#128444; This Image</div>';

  if(!imageData){
    html += '<div style="text-align:center;color:#bbb;padding:14px;font-size:11px;">Open an image to see feedback</div>';
  } else {
    var fb = generateFeedback(imageData);
    var bgCol    = fb.type==='good' ? '#e8f5e8' : fb.type==='tip' ? '#e3f2fd' : '#fffbf0';
    var bdCol    = fb.type==='good' ? '#4caf50' : fb.type==='tip' ? '#2196f3' : '#ff9800';
    var icon     = fb.type==='good' ? '&#9989;'  : fb.type==='tip' ? '&#128230;' : '&#128269;';

    html += '<div style="background:'+bgCol+';border:2px solid '+bdCol+';border-radius:8px;padding:10px 12px;margin-bottom:6px;">';
    html += '<div style="font-size:12px;font-weight:700;">'+icon+' '+fb.msg+'</div>';
    if(fb.tip){
      html += '<div style="font-size:11px;color:#555;margin-top:5px;border-top:1px solid '+bdCol+'44;padding-top:5px;">&#128073; '+fb.tip+'</div>';
    }
    html += '</div>';
  }

  html += '</div>';
  feedbackDiv.innerHTML = html;
}

async function selectStudent(name){
  currentStudent=name;
  document.querySelectorAll('.student-card').forEach(function(c){c.classList.toggle('active',c.dataset.name===name);});
  document.getElementById('h-active').textContent=name;
  updateFeedback(name, null);
  if(currentIdx>=0)await renderImage(currentIdx);
}

async function fetchMoreImages(append){
  var data=await M.images(currentPage);if(!data)return;
  totalImages=data.total;totalPages=data.pages;currentPage=data.page;
  if(!append)allImages=[];allImages=allImages.concat(data.images);
  document.getElementById('h-total').textContent=totalImages+' imgs';
}


async function openImage(idx){
  if(idx<0||idx>=allImages.length)return;
  currentIdx=idx;
  updateCounter();
  document.getElementById('img-name-label').textContent=allImages[idx];
  document.getElementById('placeholder-msg').style.display='none';
  await renderImage(idx);
}

async function renderImage(idx){
  var imgName=allImages[idx];
  var canvas=document.getElementById('viewer-canvas');
  var annot={gt_boxes:[],student_boxes:[]};

  if(currentStudent){
    var fetched=await M.annotation(currentStudent,imgName);

    // ── KEY DEBUG: log what the API returned ──────────────────
    if(fetched){
      annot=fetched;
      console.log('[ANNOT]',imgName,
        '| GT:',annot.gt_boxes.length,
        '| Student:',annot.student_boxes.length,
        annot.gt_boxes.length===0&&annot.student_boxes.length===0
          ?'⚠️ BOTH EMPTY — check /api/debug'
          :'✅');
    } else {
      console.warn('[ANNOT]',imgName,'— fetch returned null (network error?)');
    }
  }

  lastAnnot=annot;

  // Update annotation count badge
  var ab=document.getElementById('annot-badge');
  ab.style.display=currentStudent?'flex':'none';
  document.getElementById('ab-gt').textContent ='GT: '+annot.gt_boxes.length;
  document.getElementById('ab-std').textContent='You: '+annot.student_boxes.length;

  // Update feedback with real per-image metrics
  if(currentStudent){
    var row = perImageData.find(function(r){
      return r.Student === currentStudent && r.Image === imgName;
    });
    if(row){
      var imageData = {
        fn:            parseInt(row.FN)             || 0,
        fp:            parseInt(row.FP)             || 0,
        avg_iou:       parseFloat(row.Avg_IoU)      || 0,
        label_accuracy:parseFloat(row.Label_Accuracy)|| 100,
        total_gt:      parseInt(row.GT_Boxes)       || 1,
        student_count: parseInt(row.S_Boxes)        || 0
      };
      updateFeedback(currentStudent, imageData);
    } else {
      // Image not yet scored - show neutral message
      document.getElementById('feedback-content').innerHTML =
        '<div style="text-align:center;color:#999;padding:20px;font-size:12px;">No score data for this image yet.</div>';
    }
  }

  var resp=await fetch(M.imgSrc(imgName));
  var blob=await resp.blob();
  var url=URL.createObjectURL(blob);
  var img=new Image();
  img.onload=function(){
    canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
    redraw(annot,img);URL.revokeObjectURL(url);resetZoom();updateStatPills(annot);
  };
  img.src=url;canvas._baseImg=img;
}

function redraw(annot,img){
  var canvas=document.getElementById('viewer-canvas');
  var ctx=canvas.getContext('2d'),base=img||canvas._baseImg;
  if(!base)return;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.drawImage(base,0,0);
  if(showGT)  annot.gt_boxes.forEach(function(b){    drawBox(ctx,b,'#00e5c0');});
  if(showStd) annot.student_boxes.forEach(function(b){drawBox(ctx,b,'#ff4757');});
}

function drawBox(ctx,box,color){
  var xtl=box.xtl,ytl=box.ytl,xbr=box.xbr,ybr=box.ybr,label=box.label||'?';
  var w=xbr-xtl,h=ybr-ytl;
  ctx.strokeStyle=color;ctx.lineWidth=3;ctx.strokeRect(xtl,ytl,w,h);
  var fs=Math.max(12,w*0.07);
  ctx.font='bold '+fs+'px Nunito,sans-serif';
  var tw=ctx.measureText(label).width;
  ctx.fillStyle=color;
  ctx.beginPath();ctx.roundRect(xtl,ytl-fs-4,tw+12,fs+6,4);ctx.fill();
  ctx.fillStyle='#111';ctx.fillText(label,xtl+6,ytl-4);
}

function updateStatPills(annot){
  var pills=document.getElementById('stat-pills');
  if(!isAdmin){pills.innerHTML='';return;}
  var score=currentStudent?(scoreMap[currentStudent]!=null?scoreMap[currentStudent]:'—'):'—';
  pills.innerHTML=
    '<div class="stat-pill" style="background:var(--cyan)">GT: '+annot.gt_boxes.length+'</div>'+
    '<div class="stat-pill" style="background:#ffcdd2">Student: '+annot.student_boxes.length+'</div>'+
    (currentStudent?'<div class="stat-pill" style="background:var(--yellow)">Score: '+score+'%</div>':'');
}

function navImg(delta){
  if(!allImages.length)return;
  openImage(Math.max(0,Math.min(allImages.length-1,(currentIdx<0?0:currentIdx)+delta)));
}

function goToImage(){
  var input=document.getElementById('img-search');
  var targetNum=parseInt(input.value);
  if(targetNum && targetNum >= 1 && targetNum <= allImages.length){
    openImage(targetNum - 1); // Convert to 0-based index
    input.value=''; // Clear the input
  } else {
    alert('Please enter a valid image number between 1 and ' + allImages.length);
  }
}
function updateCounter(){
  document.getElementById('img-counter').textContent=
    currentIdx>=0?(currentIdx+1)+' / '+totalImages:'— / '+totalImages;
}
document.addEventListener('keydown',function(e){
  if(e.target.tagName==='INPUT')return;
  if(e.key==='ArrowRight')navImg(1);if(e.key==='ArrowLeft')navImg(-1);
  if(e.key==='+'||e.key==='=')zoomBy(1.2);if(e.key==='-')zoomBy(0.8);if(e.key==='0')resetZoom();
});

// ── Scores tab ───────────────────────────────────────────────
async function loadScoreData(){
  var results=await Promise.all([M.scores(),M.perImageScores()]);
  summaryData=results[0]||[];perImageData=results[1]||[];
  scoresLoaded=true;renderScoreView();
}

function renderScoreView(){
  var mode=document.getElementById('score-view-select').value;
  var filter=document.getElementById('score-search').value.toLowerCase().trim();
  var isSummary=(mode==='summary');
  var kpiRow=document.getElementById('score-kpi-row');
  kpiRow.style.display=isSummary?'flex':'none';
  if(isSummary&&summaryData.length){
    var avg=function(arr){return arr.reduce(function(a,b){return a+b;},0)/arr.length;};
    var sc=summaryData.map(function(r){return parseFloat(r.Overall_Score)||0;});
    var io=summaryData.map(function(r){return parseFloat(r.Avg_IoU)||0;});
    var pr=summaryData.map(function(r){return parseFloat(r.Precision)||0;});
    var re=summaryData.map(function(r){return parseFloat(r.Recall)||0;});
    kpiRow.innerHTML=kpi('Students',summaryData.length)+kpi('Avg Score',avg(sc).toFixed(1)+'%')+
      kpi('Top Score',Math.max.apply(null,sc).toFixed(1)+'%')+kpi('Avg IoU',avg(io).toFixed(3))+
      kpi('Avg Prec',avg(pr).toFixed(1)+'%')+kpi('Avg Recall',avg(re).toFixed(1)+'%');
  }
  var data=isSummary?summaryData:perImageData;
  if(filter)data=data.filter(function(r){return Object.values(r).join(' ').toLowerCase().indexOf(filter)>=0;});
  if(sortCol){data=data.slice().sort(function(a,b){
    var va=parseFloat(a[sortCol])||a[sortCol]||'',vb=parseFloat(b[sortCol])||b[sortCol]||'';
    return sortAsc?(va>vb?1:-1):(va<vb?1:-1);});}
  document.getElementById('score-row-count').textContent=data.length+' row(s)';
  if(!data.length){document.getElementById('score-table-wrap').innerHTML=
    '<div style="text-align:center;padding:60px;color:#bbb;">No results.</div>';return;}
  var cols=Object.keys(data[0]);
  var NUM={TP:1,FP:1,FN:1,Avg_IoU:1,Label_Accuracy:1,Precision:1,Recall:1,F1_Score:1,Overall_Score:1,GT_Boxes:1,S_Boxes:1,Total_GT_Boxes:1};
  var html='<table><thead><tr>';
  if(isSummary)html+='<th title="Rank by Overall Score">#</th>';
  cols.forEach(function(c){
    var arr=sortCol===c?(sortAsc?' ▲':' ▼'):'';
    var label=c.replace(/_/g,' ');
    var tip=COL_TIPS[label]||'';
    html+='<th class="'+(NUM[c]?'num':'')+'" onclick="setSort(\''+c+'\')" title="'+tip+'">'+label+arr+'</th>';
  });
  html+='</tr></thead><tbody>';
  data.forEach(function(row,i){
    html+='<tr>';
    if(isSummary){var cls=i===0?'gold':i===1?'silver':i===2?'bronze':'';
      html+='<td><span class="rank-badge '+cls+'">'+(i+1)+'</span></td>';}
    cols.forEach(function(c){
      var v=row[c];
      if(c==='Overall_Score'||c==='F1_Score'){
        var pct=parseFloat(v)||0;var col=pct>=80?'#3ddc97':pct>=50?'#ffe033':'#ff4757';
        html+='<td class="num"><div class="score-bar-wrap">'+
          '<div class="score-bar" style="width:'+Math.min(Math.round(pct),100)+'px;background:'+col+';"></div>'+
          '<span>'+pct+'%</span></div></td>';
      }else{html+='<td class="'+(NUM[c]?'num':'')+'">'+(v!=null?v:'—')+'</td>';}
    });
    html+='</tr>';
  });
  html+='</tbody></table>';
  document.getElementById('score-table-wrap').innerHTML=html;
}
function kpi(label,value){return'<div class="kpi-card"><div class="kpi-label">'+label+'</div><div class="kpi-value">'+value+'</div></div>';}
function setSort(col){if(sortCol===col)sortAsc=!sortAsc;else{sortCol=col;sortAsc=false;}renderScoreView();}
function downloadCSV(){
  var mode=document.getElementById('score-view-select').value;
  if(DATA_MODE==='flask'){window.open(mode==='summary'?'/api/scores?fmt=csv':'/api/per_image_scores?fmt=csv','_blank');}
  else{var data=mode==='summary'?summaryData:perImageData;if(!data.length)return;
    var cols=Object.keys(data[0]);
    var csv=[cols.join(',')].concat(data.map(function(r){
      return cols.map(function(c){return'"'+(r[c]!=null?r[c]:'')+'"';}).join(',');
    })).join('\n');
    var a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
    a.download=(mode==='summary'?'scores':'per_image_scores')+'.csv';a.click();}
}

// ── Analytics tab ─────────────────────────────────────────────
var PALETTE=['#9b5de5','#00e5c0','#ff4757','#ffe033','#3ddc97','#ff922b','#4dabf7','#f783ac','#69db7c','#a9e34b','#ffd43b','#74c0fc','#da77f2','#63e6be','#ff8787'];
function destroyChart(id){if(_chartInstances[id]){_chartInstances[id].destroy();delete _chartInstances[id];}}
function hideLoading(id){var el=document.getElementById(id);if(el)el.style.display='none';}
function insightBadge(cls,icon,text){return'<div class="insight-badge '+cls+'">'+icon+' '+text+'</div>';}

async function loadAnalyticsData(){
  if(!scoresLoaded){var r=await Promise.all([M.scores(),M.perImageScores()]);summaryData=r[0]||[];perImageData=r[1]||[];scoresLoaded=true;}
  analyticsLoaded=true;renderAllCharts();
}

function pct(v){return Math.round((parseFloat(v)||0)*100)/100;}

function renderAllCharts(){
  if(!summaryData.length)return;
  var sorted=summaryData.slice().sort(function(a,b){return(parseFloat(b.Overall_Score)||0)-(parseFloat(a.Overall_Score)||0);});
  var names=sorted.map(function(r){return r.Student;});
  var scores=sorted.map(function(r){return pct(r.Overall_Score);});
  var barColors=scores.map(function(s){return s>=80?'#3ddc97':s>=60?'#ffe033':s>=40?'#ff922b':'#ff4757';});
  var cd={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{family:'Nunito'},titleFont:{family:'Nunito',weight:'900'}}}};

  // Leaderboard
  destroyChart('chart-leaderboard');hideLoading('load-leaderboard');
  _chartInstances['chart-leaderboard']=new Chart(document.getElementById('chart-leaderboard'),{
    type:'bar',data:{labels:names,datasets:[{data:scores,backgroundColor:barColors,borderColor:'#111',borderWidth:2,borderRadius:6}]},
    options:Object.assign({},cd,{indexAxis:'y',scales:{x:{beginAtZero:true,max:100,ticks:{callback:function(v){return v+'%';}}},y:{ticks:{font:{family:'Nunito',weight:'700',size:11}}}}})
  });

  var top=sorted[0],bot=sorted[sorted.length-1],avg=scores.reduce(function(a,b){return a+b;},0)/scores.length;
  document.getElementById('insight-leaderboard').innerHTML=
    insightBadge('green','🥇',top.Student+' leads at '+pct(top.Overall_Score)+'%')+
    insightBadge('red','⚠️',bot.Student+' needs support at '+pct(bot.Overall_Score)+'%')+
    insightBadge('yellow','📊','Class average: '+avg.toFixed(1)+'%');

  // P vs R scatter
  destroyChart('chart-pr-scatter');hideLoading('load-pr');
  _chartInstances['chart-pr-scatter']=new Chart(document.getElementById('chart-pr-scatter'),{
    type:'scatter',
    data:{datasets:sorted.map(function(r,i){return{label:r.Student,data:[{x:pct(r.Precision),y:pct(r.Recall)}],
      backgroundColor:PALETTE[i%PALETTE.length]+'cc',borderColor:'#111',borderWidth:2,pointRadius:9,pointHoverRadius:12};})},
    options:Object.assign({},cd,{plugins:Object.assign({},cd.plugins,{legend:{display:false},tooltip:{callbacks:{label:function(ctx){return ctx.dataset.label+' — P:'+ctx.parsed.x+'% | R:'+ctx.parsed.y+'%';}}}}),
      scales:{x:{title:{display:true,text:'Precision (%)'},min:0,max:100,ticks:{callback:function(v){return v+'%';}}},
              y:{title:{display:true,text:'Recall (%)'},min:0,max:100,ticks:{callback:function(v){return v+'%';}}}}})
  });

  var bestPR=sorted.reduce(function(b,r){return(pct(r.Precision)+pct(r.Recall))>(pct(b.Precision)+pct(b.Recall))?r:b;},sorted[0]);
  var topRec=sorted.slice().sort(function(a,b){return pct(b.Recall)-pct(a.Recall);})[0];
  var topPrc=sorted.slice().sort(function(a,b){return pct(b.Precision)-pct(a.Precision);})[0];
  document.getElementById('insight-pr').innerHTML=
    insightBadge('green','⭐',bestPR.Student+' best P+R balance')+
    insightBadge('purple','🔍',topRec.Student+' top recall '+pct(topRec.Recall)+'%')+
    insightBadge('yellow','🎯',topPrc.Student+' top precision '+pct(topPrc.Precision)+'%');

  // IoU bar
  destroyChart('chart-iou');hideLoading('load-iou');
  var iouS=sorted.slice().sort(function(a,b){return(parseFloat(b.Avg_IoU)||0)-(parseFloat(a.Avg_IoU)||0);});
  _chartInstances['chart-iou']=new Chart(document.getElementById('chart-iou'),{
    type:'bar',data:{labels:iouS.map(function(r){return r.Student;}),
      datasets:[{data:iouS.map(function(r){return+(parseFloat(r.Avg_IoU)||0).toFixed(3);}),
        backgroundColor:iouS.map(function(r,i){return PALETTE[i%PALETTE.length]+'cc';}),borderColor:'#111',borderWidth:2,borderRadius:5}]},
    options:Object.assign({},cd,{scales:{y:{beginAtZero:true,max:1},x:{ticks:{font:{family:'Nunito',weight:'600',size:10},maxRotation:30}}}})
  });
  document.getElementById('insight-iou').innerHTML=insightBadge('green','📐',iouS[0].Student+' tightest boxes: IoU '+parseFloat(iouS[0].Avg_IoU).toFixed(3));

  // Recall bar
  destroyChart('chart-recall');hideLoading('load-recall');
  var recS=sorted.slice().sort(function(a,b){return pct(b.Recall)-pct(a.Recall);});
  _chartInstances['chart-recall']=new Chart(document.getElementById('chart-recall'),{
    type:'bar',data:{labels:recS.map(function(r){return r.Student;}),
      datasets:[{data:recS.map(function(r){return pct(r.Recall);}),
        backgroundColor:recS.map(function(r){var v=pct(r.Recall);return v>=80?'#3ddc97cc':v>=60?'#ffe033cc':'#ff4757cc';}),borderColor:'#111',borderWidth:2,borderRadius:5}]},
    options:Object.assign({},cd,{scales:{y:{beginAtZero:true,max:100,ticks:{callback:function(v){return v+'%';}}},x:{ticks:{font:{family:'Nunito',weight:'600',size:10},maxRotation:30}}}})
  });
  document.getElementById('insight-recall').innerHTML=
    insightBadge('green','🔍',recS[0].Student+' finds most objects ('+pct(recS[0].Recall)+'%)')+
    insightBadge('red','❌',recS[recS.length-1].Student+' misses most ('+pct(recS[recS.length-1].Recall)+'% recall)');

  // Precision bar
  destroyChart('chart-precision');hideLoading('load-precision');
  var prcS=sorted.slice().sort(function(a,b){return pct(b.Precision)-pct(a.Precision);});
  _chartInstances['chart-precision']=new Chart(document.getElementById('chart-precision'),{
    type:'bar',data:{labels:prcS.map(function(r){return r.Student;}),
      datasets:[{data:prcS.map(function(r){return pct(r.Precision);}),
        backgroundColor:prcS.map(function(r){var v=pct(r.Precision);return v>=80?'#9b5de5cc':v>=60?'#ffd43bcc':'#ff6b9dcc';}),borderColor:'#111',borderWidth:2,borderRadius:5}]},
    options:Object.assign({},cd,{scales:{y:{beginAtZero:true,max:100,ticks:{callback:function(v){return v+'%';}}},x:{ticks:{font:{family:'Nunito',weight:'600',size:10},maxRotation:30}}}})
  });
  document.getElementById('insight-precision').innerHTML=
    insightBadge('purple','🎯',prcS[0].Student+' most precise ('+pct(prcS[0].Precision)+'%)')+
    insightBadge('yellow','📌','High precision = fewer false boxes drawn');

  // Errors stacked
  destroyChart('chart-errors');hideLoading('load-errors');
  _chartInstances['chart-errors']=new Chart(document.getElementById('chart-errors'),{
    type:'bar',data:{labels:names,datasets:[
      {label:'TP (Correct)',data:sorted.map(function(r){return parseInt(r.TP)||0;}),backgroundColor:'#3ddc97cc',borderColor:'#111',borderWidth:1.5},
      {label:'FP (Extra/Wrong)',data:sorted.map(function(r){return parseInt(r.FP)||0;}),backgroundColor:'#ff4757cc',borderColor:'#111',borderWidth:1.5},
      {label:'FN (Missed)',data:sorted.map(function(r){return parseInt(r.FN)||0;}),backgroundColor:'#ff922bcc',borderColor:'#111',borderWidth:1.5},
    ]},
    options:Object.assign({},cd,{plugins:Object.assign({},cd.plugins,{legend:{display:true,position:'top',labels:{font:{family:'Nunito',weight:'700'},boxWidth:14}}}),
      scales:{x:{stacked:true,ticks:{font:{family:'Nunito',weight:'600',size:10},maxRotation:30}},y:{stacked:true}}})
  });

  // Radar top-5
  destroyChart('chart-radar');hideLoading('load-radar');
  var top5=sorted.slice(0,Math.min(5,sorted.length));
  _chartInstances['chart-radar']=new Chart(document.getElementById('chart-radar'),{
    type:'radar',
    data:{labels:['F1 Score','Precision','Recall','IoU ×100','Label Accuracy'],
      datasets:top5.map(function(r,i){return{label:r.Student,
        data:[pct(r.F1_Score),pct(r.Precision),pct(r.Recall),+(parseFloat(r.Avg_IoU)||0).toFixed(3)*100,pct(r.Label_Accuracy)],
        borderColor:PALETTE[i],backgroundColor:PALETTE[i]+'22',borderWidth:2.5,
        pointBackgroundColor:PALETTE[i],pointBorderColor:'#111',pointBorderWidth:1.5,pointRadius:4};})},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:true,position:'right',labels:{font:{family:'Nunito',weight:'700',size:11},boxWidth:14}}},
      scales:{r:{beginAtZero:true,max:100,min:0,ticks:{stepSize:20,font:{size:10}},pointLabels:{font:{family:'Nunito',weight:'700',size:11}}}}}
  });
}

boot();
</script>
</body>
</html>"""

# Flask app setup
app = Flask(__name__)

def build_html(mode="flask"):
    """Build dashboard HTML"""
    return (DASHBOARD_HTML
            .replace("__DATA_MODE__", mode)
            .replace("__ADMIN_HASH__", ADMIN_HASH))

@app.route("/")
def index():
    return Response(build_html("flask"), mimetype="text/html")

@app.route("/api/students")
def api_students():
    return jsonify(sorted(all_student_annots.keys()))

@app.route("/api/images")
def api_images():
    page = int(request.args.get("page", 0))
    start = page * PAGE_SIZE
    return jsonify({
        "images": image_list[start:start + PAGE_SIZE],
        "total": len(image_list),
        "page": page,
        "pages": (len(image_list) + PAGE_SIZE - 1) // PAGE_SIZE,
    })

@app.route("/api/scores")
def api_scores():
    fmt = request.args.get("fmt", "json")
    df = pd.read_csv(BASE_DIR / "scores.csv")
    if fmt == "csv":
        return (df.to_csv(index=False), 200,
                {"Content-Type": "text/csv",
                 "Content-Disposition": "attachment; filename=scores.csv"})
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/per_image_scores")
def api_per_image_scores():
    fmt = request.args.get("fmt", "json")
    df = pd.read_csv(BASE_DIR / "per_image_scores.csv")
    if fmt == "csv":
        return (df.to_csv(index=False), 200,
                {"Content-Type": "text/csv",
                 "Content-Disposition": "attachment; filename=per_image_scores.csv"})
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/annotation/<student>/<path:image_name>")
def api_annotation(student, image_name):
    try:
        s_annot = all_student_annots.get(student, {})
        s_boxes = lookup(s_annot, image_name, _img_stem_map)
        g_boxes = lookup(gt_annotations, image_name, _img_stem_map)
        
        def fmt(b):
            return {"label": b[0], "xtl": b[1], "ytl": b[2], "xbr": b[3], "ybr": b[4]}
        
        return jsonify({
            "student_boxes": [fmt(b) for b in s_boxes],
            "gt_boxes": [fmt(b) for b in g_boxes],
        })
    except Exception as e:
        return jsonify({"student_boxes": [], "gt_boxes": [], "error": str(e)}), 200

@app.route("/api/image/<path:image_name>")
def api_image(image_name):
    path = IMG_DIR / image_name
    if not path.exists():
        abort(404)
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return send_file(buf, mimetype="image/jpeg",
                         download_name=image_name.split("/")[-1])
    except Exception:
        return send_file(path)

def run_flask():
    """Run Flask app"""
    app.run(port=5000, debug=False, use_reloader=False)

def start_dashboard():
    """Start the dashboard in a separate thread"""
    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    
    print_header("DASHBOARD LAUNCHED")
    print("Dashboard URL: http://localhost:5000")
    print(f"Admin password: {ADMIN_PASSWORD}")
    print("Triple-click logo to unlock admin features")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        # Keep the main thread alive
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")

def main():
    """Main entry point"""
    print_header("ANNOTCHECK DESKTOP")
    print("Annotation Quality Assessment Tool")
    print("Local Desktop Version")
    
    try:
        # Step 1: Extract ZIP files
        if not extract_zip_files():
            print("Extraction failed. Please check your files and try again.")
            return
        
        # Step 2: Score annotations
        if not score_annotations():
            print("Scoring failed. Please check your data and try again.")
            return
        
        # Step 3: Load dashboard data
        load_dashboard_data()
        
        # Step 4: Start dashboard
        start_dashboard()
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("Please check the error message and try again.")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
