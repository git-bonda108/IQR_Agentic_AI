"""Find the WEBI run timestamp in the certified TB Summary tab (single file, fast)."""
import openpyxl
from pathlib import Path
p = Path("data/input/iqr_build_package/03_source_evidence/control_10032_consolidation_recon/RP-ERPODW-INC-Cons_Trial_Balance__Fin_Close_-_Reviewed.xlsx")
wb = openpyxl.load_workbook(p, data_only=True)
for sn in ("Summary", "Query Details"):
    ws = wb[sn]
    print(f"-- {sn} ({ws.dimensions}) --", flush=True)
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None:
                print(f"  {c.coordinate}: {str(c.value)[:140]!r}", flush=True)
