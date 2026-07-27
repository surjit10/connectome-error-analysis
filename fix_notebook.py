import json

file_path = "1-flywire-missing-synapse (1).ipynb"
with open(file_path, "r") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        source = cell["source"]
        new_source = []
        for line in source:
            # Fix rate_str generation
            if 'rate_str = f"{int(err_rate * 100)}_percent"' in line:
                line = line.replace('f"{int(err_rate * 100)}_percent"', 'f"{err_rate * 100:g}".replace(\'.\', \'_\') + "_percent"')
            
            # Fix percentage formatting
            if '{err_rate * 100:.1f}%' in line:
                line = line.replace('{err_rate * 100:.1f}%', '{err_rate * 100:g}%')
            if '{err_rate*100:.1f}%' in line:
                line = line.replace('{err_rate*100:.1f}%', '{err_rate*100:g}%')

            # Fix Cell 11 hardcoded folders
            if "print(f'  |-- 0_percent/trial_001..N/')" in line:
                line = "for rate in EXPERIMENT['error']['rates']:\n    print(f'  |-- {f\"{rate * 100:g}\".replace(\".\", \"_\")}_percent/trial_001..N/')\n"
            elif "print(f'  |-- 10_percent/trial_001..N/')" in line:
                continue # delete
            elif "print(f'  |-- 20_percent/trial_001..N/')" in line:
                continue # delete
                
            new_source.append(line)
        cell["source"] = new_source

with open(file_path, "w") as f:
    json.dump(nb, f, indent=1)

print("Notebook updated successfully.")
