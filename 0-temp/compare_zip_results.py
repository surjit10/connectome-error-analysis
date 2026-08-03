"""Compare the zip-extracted data (0-temp/zip_verify) against results/.

Trial layout (verified):
    results/BANC/<em>/<rate>_percent/trial_XXX/BANC_<timestamp>/
        summary.csv, trial_results.csv, runtime_report.txt,
        metadata.json, config_snapshot.yaml, README.md

For every trial artifact under both trees, compare MD5.  Also census
rates/trials per model so any missing data is obvious.
"""
import hashlib
from pathlib import Path

ZIP = Path("/home/surjit/Desktop/flywire/v1/0-temp/zip_verify/results/BANC")
RES = Path("/home/surjit/Desktop/flywire/v1/results/BANC")

MODELS = ["missed_synapses", "false_synapses", "synapse_count_measurement"]
ARTIFACTS = ["summary.csv", "trial_results.csv", "runtime_report.txt",
             "metadata.json", "config_snapshot.yaml", "README.md"]


def sha(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def collect(base: Path) -> dict:
    """Map (em, rate_dir, trial, artifact) -> path (one level deeper: timestamp dir)."""
    out = {}
    if not base.exists():
        return out
    for em in MODELS:
        em_dir = base / em
        if not em_dir.exists():
            continue
        for rate_dir in em_dir.glob("*_percent"):
            if not rate_dir.is_dir():
                continue
            for trial in rate_dir.glob("trial_*"):
                if not trial.is_dir():
                    continue
                # artifacts live inside trial_XXX/<timestamp>/
                for ts_dir in trial.iterdir():
                    if not ts_dir.is_dir():
                        continue
                    for art in ARTIFACTS:
                        f = ts_dir / art
                        if f.exists():
                            out[(em, rate_dir.name, trial.name, art)] = f
    return out


def main():
    zip_files = collect(ZIP)
    res_files = collect(RES)

    print(f"ZIP trial artifacts : {len(zip_files)}  (expect 150 trials x 6 = 900)")
    print(f"RES trial artifacts : {len(res_files)}")

    zip_keys = set(zip_files)
    res_keys = set(res_files)

    missing_in_res = zip_keys - res_keys
    extra_in_res = res_keys - zip_keys

    print(f"\nMissing in results/ (present in zips): {len(missing_in_res)}")
    for k in sorted(missing_in_res)[:15]:
        print(f"   {k}")
    print(f"Extra in results/ (not in zips): {len(extra_in_res)}")
    for k in sorted(extra_in_res)[:15]:
        print(f"   {k}")

    shared = zip_keys & res_keys
    mismatched = []
    for k in sorted(shared):
        if sha(zip_files[k]) != sha(res_files[k]):
            mismatched.append(k)
    print(f"\nShared artifacts compared : {len(shared)}")
    print(f"Content MISMATCHES        : {len(mismatched)}")
    for k in mismatched[:15]:
        print(f"   {k}")

    print("\n=== PER MODEL CENSUS (zips) ===")
    for em in MODELS:
        trials_per_rate = {}
        for k in zip_keys:
            if k[0] == em:
                trials_per_rate.setdefault(k[1], set()).add(k[2])
        n_rates = len(trials_per_rate)
        n_trials = sum(len(v) for v in trials_per_rate.values())
        print(f"{em}: {n_rates} rates / {n_trials} trials")
        for r in sorted(trials_per_rate, key=lambda x: float(x.replace('_percent', '').replace('_', '.'))):
            print(f"   {r}: {len(trials_per_rate[r])} trials")

    ok = (not missing_in_res) and (not mismatched) and len(shared) == 900
    print("\n" + "=" * 55)
    print("✅ ZIP == RESULTS for all 900 trial artifacts" if ok
          else "❌ MISMATCHES FOUND — see above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
