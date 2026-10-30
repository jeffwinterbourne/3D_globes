"""Test executing cells of working/paleo_globes_workflow.ipynb."""
import json
import sys

nb = json.load(open("working/paleo_globes_workflow.ipynb", "r", encoding="utf-8"))
print(f"Total cells: {len(nb['cells'])}")

# Environment dict for execution
env = {}

for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        # Skip interactive preview cells (which need manual display) and full batch loop
        if "generated_models[preview_key].preview()" in src:
            print(f"Cell {i}: Skipping interactive preview execution in headless test.")
            continue
        if "for idx, (key, cfg) in enumerate(PALEO_GLOBES.items()" in src:
            print(f"Cell {i}: Testing single globe build instead of full batch loop in test.")
            test_loop = """
# Test single globe build
key = list(PALEO_GLOBES.keys())[0]
cfg = PALEO_GLOBES[key]
print(f"Testing build for {key}: {cfg['name']} ({cfg['age_ma']} Ma)...")
model, meta = build_paleo_globe(key, cfg, GLOBAL_SETTINGS, pm, cmap, norm, palette_4)
print(f"Successfully built {key}! Vertices: outer={len(model.outer.vertices):,}, inner={len(model.inner.vertices):,}")
"""
            exec(test_loop, env)
            continue
        
        # Filter out %load_ext and %autoreload
        filtered_lines = [l for l in cell["source"] if not l.startswith("%")]
        code_str = "".join(filtered_lines)
        print(f"Cell {i}: Executing...")
        exec(code_str, env)
        print(f"Cell {i}: Completed successfully.")

print("\nALL TESTED CELLS EXECUTED WITH ZERO ERRORS!")
