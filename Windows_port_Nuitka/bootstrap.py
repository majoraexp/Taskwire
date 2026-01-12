import os
import sys
import urllib.request
import zipfile
import shutil
import subprocess

# URL for Python 3.11.9 Nuget Package (Contains full headers/libs)
PYTHON_URL = "https://www.nuget.org/api/v2/package/python/3.11.9"
DEST_DIR = "python_dist"
PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

def download_file(url, dest):
    print(f"Downloading {url}...")
    try:
        with urllib.request.urlopen(url) as response, open(dest, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        sys.exit(1)

def setup_python():
    # 1. Download & Extract Python if missing
    if not os.path.exists(DEST_DIR):
        print(f"Setting up Portable Python 3.11 in {DEST_DIR}...")
        os.makedirs(DEST_DIR, exist_ok=True)
        zip_path = "python.zip"
        
        download_file(PYTHON_URL, zip_path)
        
        print("Extracting Python (Nuget Package)...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Nuget package has python in 'tools/' folder. We need to extract that to DEST_DIR.
                for file in zip_ref.namelist():
                    if file.startswith("tools/"):
                        # Remove 'tools/' prefix
                        target_path = os.path.join(DEST_DIR, file[6:])
                        if not file.endswith('/'): # Skip directories if empty
                            # Ensure dir exists
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with zip_ref.open(file) as source, open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
        except Exception as e:
            print(f"Error extracting python: {e}")
            sys.exit(1)
        
        os.remove(zip_path)
        print("Extraction complete.")

    python_exe = os.path.abspath(os.path.join(DEST_DIR, "python.exe"))

    # 4. Install Pip (if missing)
    # Check if pip is installed by trying to import it
    try:
        subprocess.check_call([python_exe, "-c", "import pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Installing pip...")
        get_pip_path = os.path.abspath(os.path.join(DEST_DIR, "get-pip.py"))
        download_file(PIP_URL, get_pip_path)
        
        try:
            subprocess.check_call([python_exe, get_pip_path, "--no-warn-script-location"])
        except subprocess.CalledProcessError:
            print("Error: Failed to install pip.")
            sys.exit(1)
        finally:
            if os.path.exists(get_pip_path):
                os.remove(get_pip_path)
    
    # 5. Install virtualenv
    try:
        subprocess.check_call([python_exe, "-c", "import virtualenv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Installing virtualenv...")
        try:
            subprocess.check_call([python_exe, "-m", "pip", "install", "virtualenv", "--no-warn-script-location"])
        except subprocess.CalledProcessError:
            print("Error: Failed to install virtualenv.")
            sys.exit(1)
    
    print("Portable Python environment ready.")

if __name__ == "__main__":
    setup_python()
