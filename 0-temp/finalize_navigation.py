"""Finalize navigation for the regenerated results tree.

The regenerated presentation lives in the flat (intentional) hierarchy::

    results/<DATASET>/<error_model>/
        overview.html
        summary.html
        error_x/...
        trend_analysis/...

Breadcrumbs in every report link to ``{root}index.html`` (= results/BANC/index.html)
and ``{root}{em}/overview.html``. This script generates those missing pages and
removes stale per-model index.html files copied from the old zips (they reference
the deleted slug-bugged paths missedsynapses/ falsesynapses/ synapsecount/).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS = Path("/home/surjit/Desktop/flywire/v1/results")
BANC = RESULTS / "BANC"

MODELS = [
    ("missed_synapses", "Missed Synapses",
     "Simulates topological degradation from false-negative edge removal."),
    ("false_synapses", "False Synapses",
     "Simulates spurious edge insertion from candidate-based false-positive generation."),
    ("synapse_count_measurement", "Synapse Count Measurement",
     "Simulates measurement uncertainty in synaptic weight estimation via Gaussian noise."),
]

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0d1117;--surface:#161b22;--surface2:#21262d;--border:#30363d;--text:#e6edf3;
--text-muted:#8b949e;--accent:#58a6ff;--accent2:#3fb950;--radius:8px;
--font:'Inter','Segoe UI',system-ui,sans-serif}
body{font-family:var(--font);background:var(--bg);color:var(--text);padding:2rem;max-width:960px;margin:0 auto;line-height:1.5}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.brand{font-size:1.1rem;font-weight:700;color:var(--text)}
.crumb{color:var(--text-muted);font-size:0.85rem;margin:0.4rem 0 1.5rem}
.crumb .sep{margin:0 .4rem}
h1{font-size:1.5rem;margin-bottom:.25rem}
.subtitle{color:var(--text-muted);margin-bottom:1.25rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem}
.card h2{font-size:1.05rem;margin-bottom:.5rem}
.card p{color:var(--text-muted);font-size:.85rem;margin-bottom:.75rem}
.card ul{list-style:none}
.card li{margin:.3rem 0}
.tag{display:inline-block;background:var(--surface2);border:1px solid var(--border);
border-radius:999px;padding:.05rem .6rem;font-size:.72rem;color:var(--text-muted);margin-left:.4rem}
.stat{color:var(--accent2);font-weight:600}
"""


def overview_page(display, description, rate_dirs):
    rows = []
    for label in sorted(
        rate_dirs,
        key=lambda n: float(n.replace("error_", "").replace("_", ".")),
    ):
        rate = label.replace("error_", "")  # e.g. "error_0_25" -> "0_25"
        rows.append(f'<li><a href="error_{rate}/report.html">🔍 Error {rate}%</a></li>')
    rows_html = "\n".join(rows)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>{display} — Overview</title><style>{CSS}</style></head><body>
<div class="brand"><a href="../index.html">🧠 FlyWire</a> <span class="sep">/</span> {display}</div>
<div class="crumb"><a href="../index.html">Index</a><span class="sep">/</span><span>{display}</span></div>
<h1>{display}</h1><p class="subtitle">{description}</p>
<div class="card"><h2>📁 BANC</h2><ul>
<li><a href="summary.html">📄 Dataset Summary</a></li>
<li><a href="trend_analysis/trend_report.html">📈 Trend Analysis</a></li>
{rows_html}
</ul></div>
<div class="card"><h2>🔍 Cross-Dataset Analysis</h2>
<p>Cross-dataset comparisons will appear here once multiple datasets are processed.</p></div>
</body></html>"""


def dataset_index():
    cards = []
    for slug, display, desc in MODELS:
        em_dir = BANC / slug
        if not em_dir.exists():
            continue
        n_rates = len(list(em_dir.glob("error_*"))) if em_dir.exists() else 0
        cards.append(
            f'<div class="card"><h2><a href="{slug}/overview.html">{display}</a></h2>'
            f'<p>{desc}</p><ul>'
            f'<li><a href="{slug}/overview.html">🗂️ Overview</a>'
            f'<span class="tag">{n_rates} rates</span></li>'
            f'<li><a href="{slug}/summary.html">📄 Dataset Summary</a></li>'
            f'<li><a href="{slug}/trend_analysis/trend_report.html">📈 Trend Analysis</a></li>'
            f"</ul></div>"
        )
    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>BANC — Dataset Index</title><style>{CSS}</style></head><body>
<div class="brand"><a href="../index.html">🧠 FlyWire</a> <span class="sep">/</span> BANC</div>
<div class="crumb"><a href="../index.html">Index</a><span class="sep">/</span><span>BANC</span></div>
<h1>Dataset: BANC</h1>
<p class="subtitle">Connectivity-perturbation experiments across three independent error models.</p>
<div class="cards">{cards_html}</div>
</body></html>"""


def root_index():
    ds_cards = []
    for ds_dir in sorted(RESULTS.iterdir()):
        if not ds_dir.is_dir() or ds_dir.name in ("comparison", ".git", "__pycache__"):
            continue
        n_models = sum(1 for m, _, _ in MODELS if (ds_dir / m).exists())
        ds_cards.append(
            f'<div class="card"><h2><a href="{ds_dir.name}/index.html">📦 {ds_dir.name}</a></h2>'
            f'<p><span class="stat">{n_models}</span> error model(s) processed.</p>'
            f'<ul><li><a href="{ds_dir.name}/index.html">Open dataset index</a></li></ul></div>'
        )
    cards_html = "\n".join(ds_cards) if ds_cards else "<p>No datasets found.</p>"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>FlyWire Analysis — Results Index</title><style>{CSS}</style></head><body>
<div class="brand">🧠 FlyWire</div>
<div class="crumb"><span>Index</span></div>
<h1>Experiment Results</h1>
<p class="subtitle">Biological error-model experiments on connectome datasets.</p>
<div class="cards">{cards_html}</div>
</body></html>"""


def main():
    # 1. Per-error-model overview.html + remove stale index.html from old zips
    for slug, display, desc in MODELS:
        em_dir = BANC / slug
        if not em_dir.exists():
            print(f"[{slug}] SKIP")
            continue
        rate_dirs = [
            d.name for d in em_dir.glob("error_*") if d.is_dir()
        ]
        (em_dir / "overview.html").write_text(
            overview_page(display, desc, rate_dirs), encoding="utf-8"
        )
        # Remove stale index.html copied from old zips (references deleted paths)
        stale = em_dir / "index.html"
        if stale.exists():
            stale.unlink()
        print(f"[{slug}] overview.html written; stale index removed ({len(rate_dirs)} rates)")

    # 2. results/BANC/index.html
    (BANC / "index.html").write_text(dataset_index(), encoding="utf-8")
    print("[BANC] index.html written")

    # 3. results/index.html
    (RESULTS / "index.html").write_text(root_index(), encoding="utf-8")
    print("[results] index.html written")


if __name__ == "__main__":
    main()
