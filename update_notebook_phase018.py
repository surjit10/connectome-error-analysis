import json

def update_notebook():
    file_path = 'experiments_missed_synapses.ipynb'
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load notebook: {e}")
        return

    for cell in data.get('cells', []):
        if not cell.get('source'):
            continue
        
        first_line = cell['source'][0]
        if first_line.startswith('# Cell 2:'):
            cell['source'] = [
                "# Cell 2: Imports (Framework Components Only)\n",
                "import os\n",
                "import zipfile\n",
                "import pandas as pd\n",
                "from pathlib import Path\n",
                "\n",
                "from core.experiment_runner import ExperimentRunner, ExperimentConfig\n",
                "from modules.error_models.error_registry import registry as error_registry\n",
                "from modules.graph_analyses.analysis_registry import registry as analysis_registry\n",
                "from modules.statistical_evaluation import StatisticalEvaluator\n",
                "from core.export_manager import ExportManager\n"
            ]
        elif first_line.startswith('# Cell 9:'):
            cell['source'] = [
                "# Cell 9: Phase 017 - Statistical Evaluation & Phase 018 - Presentation Export\n",
                "from core.checkpoint_manager import CheckpointManager\n",
                "evaluator = StatisticalEvaluator()\n",
                "aggregated_stats_by_rate = {}\n",
                "baseline_runs = [r for r in results_per_rate.get(0.00, []) if r.succeeded]\n",
                "\n",
                "for err_rate, run_results in results_per_rate.items():\n",
                "    successful_runs = [r for r in run_results if r.succeeded]\n",
                "    if successful_runs:\n",
                "        eval_result = evaluator.evaluate(baseline_runs, successful_runs)\n",
                "        aggregated_stats_by_rate[err_rate] = eval_result\n",
                "        print(f\"Evaluated stats for error rate {err_rate*100:.1f}% ({len(successful_runs)} successful trials).\")\n",
                "        \n",
                "        cm = CheckpointManager(Path(EXPERIMENT['export']['output_directory']) / 'checkpoints')\n",
                "        cm.save_phase_017_checkpoint(\n",
                "            experiment_name=f\"{EXPERIMENT['metadata']['experiment_name']}_{err_rate}\",\n",
                "            evaluation_result=eval_result,\n",
                "            validation_results=\"VALIDATED\"\n",
                "        )\n",
                "    else:\n",
                "        print(f\"No successful runs to evaluate for error rate {err_rate*100:.1f}%.\")\n",
                "\n",
                "# Phase 018: Generate Presentation Artifacts (Dashboards, Plots, ZIP)\n",
                "ExportManager().export_presentation(\n",
                "    results_by_rate=aggregated_stats_by_rate,\n",
                "    output_root=Path(EXPERIMENT['export']['output_directory']),\n",
                "    metadata=EXPERIMENT['metadata']\n",
                ")\n",
                "print(\"Phase 018 Presentation Export completed.\")\n"
            ]

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
        
if __name__ == '__main__':
    update_notebook()
