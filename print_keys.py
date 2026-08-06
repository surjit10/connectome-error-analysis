from core.data_loader import load_aggregated
from pathlib import Path
em_dir = Path("results/BANC/synapse_count_measurement/0_percent")
data = load_aggregated(em_dir)
for a_name, m_dict in data.items():
    for m_name in m_dict.keys():
        print(f"{a_name}.{m_name}")
