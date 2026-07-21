import os
import random
import csv
from pathlib import Path

def generate_dataset():
    random.seed(42)  # Fixed seed for determinism
    
    out_dir = Path("0-demodata/TEST_v1")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate Neurons
    neurons = []
    # 1000 neurons
    for i in range(1, 1001):
        root_id = 1000 + i
        region = "brain" if i <= 500 else "vnc"
        nt_type = random.choice(["acetylcholine", "glutamate", "GABA"])
        neurons.append({
            "root_id": root_id,
            "top_region": region,
            "predicted_nt_type": nt_type
        })
        
    # Generate Edges
    edges = set()
    connections = []
    
    # Hub neurons
    hubs = [1001, 1010, 1015, 1100, 1200]
    
    # 1. Connect hubs to many others
    for hub in hubs:
        targets = random.sample(range(1001, 2001), 200)
        for t in targets:
            if t != hub:
                edges.add((hub, t))
                edges.add((t, hub)) # reciprocal
                
    # 2. Add random edges to reach ~10000
    while len(edges) < 10000:
        u = random.randint(1001, 2000)
        v = random.randint(1001, 2000)
        if u != v:
            edges.add((u, v))
            
    # Format edges
    for u, v in sorted(list(edges)):
        connections.append({
            "pre_root_id": u,
            "post_root_id": v,
            "weight": random.randint(1, 10)
        })
        
    # Write neurons.csv
    with open(out_dir / "neurons.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["root_id", "top_region", "predicted_nt_type"])
        writer.writeheader()
        writer.writerows(neurons)
        
    # Write connections.csv
    with open(out_dir / "connections.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pre_root_id", "post_root_id", "weight"])
        writer.writeheader()
        writer.writerows(connections)
        
    # Write README.md
    readme_content = """# TEST_v1 Synthetic Dataset

**Purpose**: This is a deterministic, synthetic miniature dataset designed exclusively for local framework validation. It is *not* a real biological connectome.
**Size**: 1000 Neurons, 10000 Connections.
**Usage**: Do NOT use this for real scientific experiments. Its sole purpose is to test the end-to-end execution of the `FlyWire Research Framework` (Phases 001-018) rapidly without downloading the 50GB production datasets.

## Properties
- Contains multiple connected components.
- Includes reciprocal edges and hub neurons.
- Varying synaptic weights to test biological constraint calculations.
- Always identical (deterministic generation).
"""
    with open(out_dir / "README.md", "w") as f:
        f.write(readme_content)

if __name__ == "__main__":
    generate_dataset()
