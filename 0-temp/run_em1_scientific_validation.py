import sys
from pathlib import Path
from core.config_manager import ConfigManager
from core.experiment_runner import ExperimentRunner
from modules.graph_analyses.analysis_registry import registry as a_reg
from modules.error_models.common.error_registry import registry as e_reg

def main():
    cm = ConfigManager(Path("configs"))
    runner = ExperimentRunner(a_reg, e_reg)
    
    # We load standard configs generated from the yaml
    configs = cm.get_suite("missed_synapses")
    
    # Filter for BANC
    configs = [c for c in configs if c.dataset_name == "BANC"]
    
    test_rates = [0.0, 0.05, 0.2]
    test_configs = [c for c in configs if c.error_model_config.get("error_rate", 0.0) in test_rates]
    test_configs = sorted(test_configs, key=lambda c: c.error_model_config.get("error_rate", 0.0))
    
    print(f"{'Rate':>6} | {'Total Syn':>12} | {'Edge Count':>10} | {'Weight Mean':>11} | {'Weight Var':>11}")
    print("-" * 65)
    
    for config in test_configs:
        rate = config.error_model_config.get("error_rate", 0.0)
        
        # Override to just run basic_structure to be fast
        config.analysis_names = ["basic_structure"]
        if config.baseline_analysis_names:
            config.baseline_analysis_names = ["basic_structure"]
            
        result = runner.run(config)
        
        # Since run is for a single experiment (trial), we look at result.analysis_results
        metrics = None
        
        if rate == 0.0 and result.baseline_analysis_results:
             for a_res in result.baseline_analysis_results:
                 if a_res.analysis_name == "basic_structure":
                     metrics = a_res.metrics
                     break
        
        for a_res in result.analysis_results:
            if a_res.analysis_name == "basic_structure":
                metrics = a_res.metrics
                break
                
        if metrics:
            print(f"{rate:5.1%} | {metrics.get('total_synapses', 0):12.0f} | "
                  f"{metrics.get('edge_count', 0):10.0f} | "
                  f"{metrics.get('weight_mean', 0):11.3f} | "
                  f"{metrics.get('weight_variance', 0):11.3f}")
        else:
            print(f"{rate:5.1%} | Failed to get metrics")

if __name__ == "__main__":
    main()
