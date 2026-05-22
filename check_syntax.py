import ast, os, sys

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

files = [
    "dashboard/Home.py",
    "dashboard/components/ui.py",
    "dashboard/components/charts.py",
    "dashboard/components/maps.py",
    "dashboard/components/weather.py",
    "dashboard/components/prediction.py",
    "dashboard/pages/1_\U0001f321\ufe0f_M\xe9t\xe9o.py",
    "dashboard/pages/2_\U0001f5fa\ufe0f_Carte_GIS.py",
    "dashboard/pages/3_\U0001f6f0\ufe0f_Satellite.py",
    "dashboard/pages/4_\U0001f4c8_Climatologie.py",
    "dashboard/pages/5_\U0001f52e_Pr\xe9diction.py",
    "dashboard/pages/6_\U0001f6a8_Alertes.py",
    "dashboard/pages/7_\U0001f916_Mod\xe8le_IA.py",
]

errors = []
for f in files:
    label = f.split("/")[-1][:30]
    try:
        with open(f, encoding="utf-8") as fh:
            src = fh.read()
        ast.parse(src)
        print(f"  OK  {label}")
    except SyntaxError as e:
        print(f" ERR  {label}  ->  Line {e.lineno}: {e.msg}")
        errors.append(f)
    except FileNotFoundError:
        print(f" N/A  {label}  ->  File not found")
        errors.append(f)

print()
print(f"Result: {len(files) - len(errors)}/{len(files)} passed")
if errors:
    print("Failed files:")
    for e in errors:
        print(f"  - {e}")
