# AnnotCheck Desktop

A desktop application for evaluating student annotations against ground truth data. This tool was converted from a Google Colab notebook to run locally on your desktop.

## Features

- **ZIP File Processing**: Extract and organize student annotation files and ground truth
- **Scoring System**: Compare student annotations with ground truth using IoU, precision, recall, and F1 scores
- **Interactive Dashboard**: Web-based interface for reviewing annotations and viewing analytics
- **Local Processing**: No cloud dependencies - everything runs locally

## Installation

1. **Install Python** (3.8 or higher)
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Step 1: Prepare Your Files

1. Create a folder structure like this:
   ```
   annotcheck_deploy/
   annotcheck_desktop.py
   requirements.txt
   uploads/
   ```

2. Place your ZIP files in the `uploads` directory:
   - **Ground Truth ZIP**: Must contain "ground", "gt", or "truth" in the filename
   - **Student ZIPs**: Individual student annotation files

### Step 2: Run the Application

```bash
python annotcheck_desktop.py
```

The application will:
1. Extract and organize your ZIP files
2. Score the annotations
3. Launch a web dashboard

### Step 3: Access the Dashboard

Open your web browser and go to: **http://localhost:5000**

**Admin Access**: Triple-click the "ANNOT.CHECK" logo and enter password: `orchvate2024`

## File Structure

After running, the application creates:
```
annotation_project/
  XML/           # Student annotation files
  Ground_Truth/  # Ground truth annotation files
  Images/        # Extracted images
  scores.csv     # Summary scores per student
  per_image_scores.csv  # Detailed scores per image
```

## Scoring Metrics

- **IoU (Intersection over Union)**: Overlap quality between predicted and ground truth boxes
- **Precision**: Of all boxes drawn, what percentage were correct
- **Recall**: Of all actual objects, what percentage were found
- **F1 Score**: Harmonic mean of precision and recall
- **Overall Score**: Weighted composite score

## Dashboard Features

- **Review Tab**: View annotations side-by-side with ground truth
- **Scores Tab**: View detailed scoring results (admin only)
- **Analytics Tab**: Visual analytics and charts (admin only)

## Troubleshooting

### Common Issues

1. **"No ZIP files found"**
   - Make sure your ZIP files are in the `uploads` directory
   - Check that files have `.zip` extension

2. **"Could not identify Ground Truth ZIP"**
   - Ensure your ground truth filename contains "ground", "gt", or "truth"
   - Example: `ground_truth.zip` or `GT_annotations.zip`

3. **"NO GT BOXES FOUND"**
   - Check that image filenames in your XMLs match the actual image files
   - Ensure XML files are in CVAT format

4. **Dashboard not loading**
   - Check that port 5000 is not already in use
   - Make sure all dependencies are installed

### File Format Requirements

**XML Format (CVAT)**:
```xml
<image name="image1.jpg">
  <box label="person" xtl="100" ytl="50" xbr="200" ybr="300"/>
  <box label="car" xtl="300" ytl="100" xbr="500" ybr="250"/>
</image>
```

**ZIP Structure**:
- Ground Truth ZIP should contain XML files
- Student ZIPs should contain XML files and optionally images

## Advanced Usage

### Command Line Options

The application can be modified to support command line arguments. Edit the `main()` function in `annotcheck_desktop.py` to add custom options.

### Custom Scoring Thresholds

Modify the `IOU_THRESHOLD` constant in the code to adjust matching sensitivity:
- Higher values (0.7-0.9): Stricter matching
- Lower values (0.3-0.5): More lenient matching

### Batch Processing

For processing multiple datasets, you can modify the script to accept directory paths as command line arguments.

## Support

If you encounter issues:
1. Check the console output for error messages
2. Verify your file formats match the requirements
3. Ensure all dependencies are properly installed
4. Check that your ZIP files are not corrupted

## License

This software is provided as-is for educational and research purposes.
