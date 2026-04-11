#!/usr/bin/env python3
"""
Download images from Azure Blob Storage for AnnotCheck Desktop
"""

import os
import sys
from pathlib import Path

# Install azure-storage-blob if not available
try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    print("Installing azure-storage-blob...")
    os.system(f"{sys.executable} -m pip install azure-storage-blob")
    from azure.storage.blob import BlobServiceClient

# Configuration
ACCOUNT_NAME = "opencvatstorage"
CONTAINER_NAME = "opencvatcontainer"
BLOB_PREFIX = "ML_Model/Clean_Dataset/complex2/Dataset_1/"
SAS_TOKEN = "sp=rl&st=2026-04-10T18:10:40Z&se=2026-04-25T02:25:40Z&spr=https&sv=2025-11-05&sr=c&sig=bSjzXcqyrQED8FQxRhw8D%2FAGwypNljZJKlJLOiVlXgU%3D"

# Desktop paths
BASE_DIR = Path(__file__).parent / "annotation_project"
IMG_DIR = BASE_DIR / "Images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

def download_images():
    """Download images from Azure Blob Storage"""
    print("=" * 60)
    print("DOWNLOADING IMAGES FROM AZURE BLOB STORAGE")
    print("=" * 60)
    
    # Connect to Azure
    account_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net?{SAS_TOKEN}"
    client = BlobServiceClient(account_url=account_url)
    container = client.get_container_client(CONTAINER_NAME)
    
    # List and download images
    blobs = list(container.list_blobs(name_starts_with=BLOB_PREFIX))
    image_blobs = [b for b in blobs if b.name.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    print(f"Found {len(image_blobs)} images in Azure. Downloading...\n")
    
    downloaded = 0
    skipped = 0
    
    for i, blob in enumerate(image_blobs):
        filename = os.path.basename(blob.name)
        dst = IMG_DIR / filename
        
        if dst.exists():
            skipped += 1
            continue
        
        try:
            blob_client = container.get_blob_client(blob.name)
            with open(dst, "wb") as f:
                f.write(blob_client.download_blob().readall())
            downloaded += 1
            
            if (i + 1) % 50 == 0 or (i + 1) == len(image_blobs):
                print(f"  Downloaded {downloaded + skipped}/{len(image_blobs)} images")
                
        except Exception as e:
            print(f"  Error downloading {filename}: {e}")
    
    print(f"\nDone! {downloaded} new images downloaded, {skipped} skipped")
    print(f"Total images in {IMG_DIR}: {len(list(IMG_DIR.glob('*.jpg')) + list(IMG_DIR.glob('*.jpeg')) + list(IMG_DIR.glob('*.png')))}")

if __name__ == "__main__":
    download_images()
