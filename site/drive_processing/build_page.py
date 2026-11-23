"""Regenerate the current complete dashboard from template.html and data.json."""
import json
from pathlib import Path
tpl = Path("template.html").read_text(encoding="utf-8")
if tpl.count("__DATA__") != 1:
    raise ValueError("The template must contain exactly one __DATA__ placeholder")
data = json.loads(Path("data.json").read_text(encoding="utf-8"))
forecast = Path("forecasts.json")
if forecast.exists():
    data["forecasts"] = json.loads(forecast.read_text(encoding="utf-8"))
encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
bigdata_file = Path("bigdata.json")
bigdata = json.loads(bigdata_file.read_text(encoding="utf-8")) if bigdata_file.exists() else {"series": []}
bigdata.pop("monitor", None)  # The map reads bigdata_heatmap.json separately.
big_encoded = json.dumps(bigdata, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
page = tpl.replace("__DATA__", encoded).replace("__BIGDATA__", big_encoded)
Path("espana.html").write_text(page, encoding="utf-8")
Path("artifact.html").write_text(page, encoding="utf-8")
print("espana.html and artifact.html regenerated")
