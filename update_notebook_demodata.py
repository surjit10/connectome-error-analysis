import json

def update_notebook():
    file_path = 'experiments_missed_synapses.ipynb'
    with open(file_path, 'r') as f:
        data = json.load(f)

    for cell in data.get('cells', []):
        if not cell.get('source'):
            continue
        
        first_line = cell['source'][0]
        if first_line.startswith('# Cell 3:'):
            # Change DATASET = "MANC" to DATASET = "TEST"
            for i, line in enumerate(cell['source']):
                if 'EXPERIMENT = {' in line:
                    break
                if 'DATASET =' in line or 'dataset_name =' in line:
                    cell['source'][i] = 'dataset_name = "TEST"\n'
            
            for i, line in enumerate(cell['source']):
                if '"name": "MANC"' in line:
                    cell['source'][i] = line.replace('"MANC"', '"TEST"')
                if '"output_directory": "/kaggle/working/results"' in line:
                    cell['source'][i] = line.replace('"/kaggle/working/results"', '"results"')
                    
        elif first_line.startswith('# Cell 4:'):
            cell['source'] = [
                "# Cell 4: Locate & Extract Dataset\n",
                "import os\n",
                "import zipfile\n",
                "from pathlib import Path\n",
                "\n",
                "ds_name = EXPERIMENT['dataset']['name']\n",
                "DATASET_ROOT = None\n",
                "\n",
                "# Check for local demodata first (for local validation)\n",
                "if os.path.exists('0-demodata'):\n",
                "    for entry in os.listdir('0-demodata'):\n",
                "        if entry.upper().startswith(ds_name.upper()):\n",
                "            DATASET_ROOT = '0-demodata'\n",
                "            print(f\"Local demo dataset detected at {DATASET_ROOT}\")\n",
                "            break\n",
                "\n",
                "# Fallback to Kaggle ZIP extraction\n",
                "if not DATASET_ROOT:\n",
                "    KAGGLE_INPUT_DIR = '/kaggle/input'\n",
                "    KAGGLE_WORKING_DIR = '/kaggle/working/extracted_datasets'\n",
                "    zip_files = []\n",
                "    if os.path.exists(KAGGLE_INPUT_DIR):\n",
                "        for root, _, files in os.walk(KAGGLE_INPUT_DIR):\n",
                "            for file in files:\n",
                "                if file.endswith('.zip'):\n",
                "                    zip_files.append(os.path.join(root, file))\n",
                "    \n",
                "    if len(zip_files) == 0:\n",
                "        raise FileNotFoundError(\"CRITICAL: No dataset ZIP files found in /kaggle/input and no local demodata found.\")\n",
                "    elif len(zip_files) > 1:\n",
                "        print(\"Multiple ZIP files detected:\")\n",
                "        for z in zip_files:\n",
                "            print(f\" - {z}\")\n",
                "        raise ValueError(\"CRITICAL: Multiple ZIP files found. Please manually specify which archive to use or remove duplicates.\")\n",
                "    else:\n",
                "        dataset_zip_path = zip_files[0]\n",
                "        print(f\"Dataset ZIP automatically detected: {dataset_zip_path}\")\n",
                "        print(\"Extracting archive... this may take a moment.\")\n",
                "        os.makedirs(KAGGLE_WORKING_DIR, exist_ok=True)\n",
                "        with zipfile.ZipFile(dataset_zip_path, 'r') as zip_ref:\n",
                "            zip_ref.extractall(KAGGLE_WORKING_DIR)\n",
                "        print(f\"Successfully extracted to {KAGGLE_WORKING_DIR}\")\n",
                "        DATASET_ROOT = KAGGLE_WORKING_DIR\n"
            ]
        elif first_line.startswith('# Cell 5:'):
            cell['source'] = [
                "# Cell 5: Verify Dataset Structure\n",
                "from core.dataset_registry import DatasetRegistry, DatasetRegistryError\n",
                "\n",
                "try:\n",
                "    registry = DatasetRegistry(configs_root='configs', dataset_root=DATASET_ROOT)\n",
                "    resolved_dir = registry.resolve_dataset_dir(ds_name, DATASET_ROOT)\n",
                "    print(f\"Verified dataset structure. Resolved directory: {resolved_dir}\")\n",
                "except DatasetRegistryError as e:\n",
                "    raise FileNotFoundError(f\"CRITICAL: Could not resolve dataset folder for '{ds_name}' in '{DATASET_ROOT}'.\") from e\n"
            ]
        elif first_line.startswith('# Cell 8:'):
            # Change output directory for TEST to just local results
            for i, line in enumerate(cell['source']):
                if 'EXPERIMENT["export"]["output_directory"]' in line:
                    # leave as is, since output_directory in EXPERIMENT is /kaggle/working/results
                    pass

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    update_notebook()
