import os
import glob
import pytest
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

def get_notebooks():
    """Finds all Jupyter notebooks in the examples directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    notebooks = glob.glob(os.path.join(base_dir, "examples", "**", "*.ipynb"), recursive=True)
    # Filter out checkpoint files
    notebooks = [n for n in notebooks if ".ipynb_checkpoints" not in n]
    return notebooks

@pytest.mark.parametrize("notebook_path", get_notebooks())
def test_notebook_execution(notebook_path):
    """Executes a Jupyter notebook end-to-end to verify no NameError or other exceptions are raised."""
    notebook_dir = os.path.dirname(notebook_path)
    
    with open(notebook_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
        
    # Set timeout to 10 minutes to allow downloads/processing
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    
    try:
        ep.preprocess(nb, {"metadata": {"path": notebook_dir}})
    except Exception as e:
        pytest.fail(f"Notebook {os.path.basename(notebook_path)} failed to execute:\n{e}")
