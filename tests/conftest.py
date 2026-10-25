"""Point every pipeline path at a scratch directory before the pipeline modules are imported."""
import os
import sys
import tempfile
from pathlib import Path

_scratch = Path(tempfile.mkdtemp(prefix="stock-pipeline-test-"))
os.environ["STOCK_RAW_DIR"] = str(_scratch / "raw")
os.environ["STOCK_WAREHOUSE_DB"] = str(_scratch / "warehouse.duckdb")
os.environ["STOCK_SITE_DATA"] = str(_scratch / "site-data")
(_scratch / "raw").mkdir()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
