#!/usr/bin/env bash
# ===========================================================================
# cleanup_duplicates.sh
# ===========================================================================
# Removes old-location files that were moved during the preprocessing
# architecture refactoring.  Safe to run multiple times — only removes
# files that exist.
#
# Usage:
#   chmod +x cleanup_duplicates.sh
#   ./cleanup_duplicates.sh
#
# What it removes (if still present):
#
#   modules/preprocessing/
#       metadata.py           → moved to common/metadata.py
#       validator.py          → moved to common/validator.py
#       lookup.py             → moved to common/lookup.py
#       prepared_graph.py     → moved to common/prepared_graph.py
#       pipeline.py           → moved to common/pipeline.py
#       biological_features.py → moved to missed_synapses/
#
#   modules/error_models/
#       vulnerability.py      → moved to preprocessing/missed_synapses/
#       base_model.py         → deleted (empty stub — superseded by
#                                base_error_model.py)
#
#   modules/graph_analyses/
#       community_detection.py → deleted (empty stub — never implemented)
# ===========================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Files to remove (old locations) ───────────────────────────────────────
FILES=(
    # Preprocessing — moved to common/
    "$ROOT/modules/preprocessing/metadata.py"
    "$ROOT/modules/preprocessing/validator.py"
    "$ROOT/modules/preprocessing/lookup.py"
    "$ROOT/modules/preprocessing/prepared_graph.py"
    "$ROOT/modules/preprocessing/pipeline.py"
    # Preprocessing — moved to missed_synapses/
    "$ROOT/modules/preprocessing/biological_features.py"
    # Error models — moved to preprocessing/missed_synapses/
    "$ROOT/modules/error_models/vulnerability.py"
    # Error models — deleted (empty stub)
    "$ROOT/modules/error_models/base_model.py"
    # Graph analyses — deleted (empty stub)
    "$ROOT/modules/graph_analyses/community_detection.py"
)

# ── Verify new locations exist (safety check) ──────────────────────────────
NEW_FILES=(
    "$ROOT/modules/preprocessing/common/metadata.py"
    "$ROOT/modules/preprocessing/common/validator.py"
    "$ROOT/modules/preprocessing/common/lookup.py"
    "$ROOT/modules/preprocessing/common/prepared_graph.py"
    "$ROOT/modules/preprocessing/common/pipeline.py"
    "$ROOT/modules/preprocessing/missed_synapses/biological_features.py"
    "$ROOT/modules/preprocessing/missed_synapses/vulnerability.py"
)

echo "=== Checking new locations exist ==="
ALL_NEW_OK=true
for nf in "${NEW_FILES[@]}"; do
    if [ -f "$nf" ]; then
        echo "  ✅ $(basename "$(dirname "$nf")")/$(basename "$nf")"
    else
        echo "  ❌ MISSING: $nf"
        ALL_NEW_OK=false
    fi
done

if [ "$ALL_NEW_OK" = false ]; then
    echo ""
    echo "ERROR: One or more new-location files are missing."
    echo "Aborting cleanup — do not remove old files without new ones in place."
    exit 1
fi

# ── Remove old files ──────────────────────────────────────────────────────
echo ""
echo "=== Removing old-location files ==="
REMOVED=0
MISSING=0
for f in "${FILES[@]}"; do
    if [ -f "$f" ]; then
        rm -v "$f"
        REMOVED=$((REMOVED + 1))
    else
        MISSING=$((MISSING + 1))
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=== Cleanup Summary ==="
echo "  Removed : $REMOVED file(s)"
echo "  Already gone : $MISSING file(s)"
echo ""
if [ "$REMOVED" -eq 0 ] && [ "$MISSING" -eq "${#FILES[@]}" ]; then
    echo "✅ All clean — no duplicate files remain after restructure."
elif [ "$REMOVED" -gt 0 ]; then
    echo "✅ Removed $REMOVED leftover file(s). Run again to verify."
else
    echo "⚠️  Some files could not be found or removed."
fi
