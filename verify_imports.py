"""逐个导入 53 个非标准库依赖，报告缺哪个。

用法：
    .venv\\Scripts\\python.exe verify_imports.py
"""

import importlib
import sys

# import 名 -> 说明（pip 包名）
MODULES = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("scipy", "scipy"),
    ("matplotlib", "matplotlib"),
    ("requests", "requests"),
    ("skimage", "scikit-image"),
    ("Bio", "biopython"),
    ("cv2", "opencv-python-headless"),
    ("sklearn", "scikit-learn"),
    ("FlowCytometryTools", "FlowCytometryTools"),
    ("flowkit", "flowkit"),
    ("torch", "torch"),
    ("SimpleITK", "SimpleITK"),
    ("bs4", "beautifulsoup4"),
    ("gseapy", "gseapy"),
    ("langchain_core", "langchain-core"),
    ("nibabel", "nibabel"),
    ("nilearn", "nilearn"),
    ("trackpy", "trackpy"),
    ("DeepPurpose", "DeepPurpose"),
    ("PyPDF2", "PyPDF2"),
    ("accelerate", "accelerate"),
    ("anthropic", "anthropic"),
    ("arxiv", "arxiv"),
    ("cellpose", "cellpose"),
    ("cobra", "cobra"),
    ("cooler", "cooler"),
    ("esm", "fair-esm"),
    ("gget", "gget"),
    ("googlesearch", "googlesearch-python"),
    ("harmony", "harmonypy"),
    ("libsbml", "python-libsbml"),
    ("msprime", "msprime"),
    ("networkx", "networkx"),
    ("nnunet", "nnunet"),
    ("popv", "popv"),
    ("pybedtools", "pybedtools"),
    ("pybiomart", "pybiomart"),
    ("pykalman", "pykalman"),
    ("pyliftover", "pyliftover"),
    ("pymed", "pymed"),
    ("rdkit", "rdkit"),
    ("reportlab", "reportlab"),
    ("scanpy", "scanpy"),
    ("scholarly", "scholarly"),
    ("scvi", "scvi-tools"),
    ("statsmodels", "statsmodels"),
    ("tdc", "PyTDC"),
    ("tqdm", "tqdm"),
    ("transformers", "transformers"),
    ("community", "python-louvain"),
    ("RNA", "ViennaRNA"),
    ("eval_single_anndata", "UCE 仓库（非 PyPI）"),
]

ok, missing = [], []
for name, pkg in MODULES:
    try:
        importlib.import_module(name)
        ok.append((name, pkg))
    except Exception as e:  # noqa: BLE001
        missing.append((name, pkg, f"{type(e).__name__}: {e}"[:90]))

print(f"可导入 {len(ok)} / {len(MODULES)}")
print()
if missing:
    print("缺失或导入失败：")
    for name, pkg, err in missing:
        print(f"  {name:<24} (pip: {pkg})")
        print(f"      {err}")

if "--quiet" not in sys.argv:
    print()
    print("已就绪：" + ", ".join(n for n, _ in ok))
