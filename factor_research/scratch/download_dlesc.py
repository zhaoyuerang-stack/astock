import urllib.request
import os
from pathlib import Path

urls = {
    "dlesc_clustering.py": "https://raw.githubusercontent.com/hugo2046/QuantsPlaybook/master/B-%E5%9B%A0%E5%AD%90%E6%9E%84%E5%BB%BA%E7%B1%BB/%E5%9F%BA%E4%BA%8E%E9%9A%94%E5%A4%9C%E4%B8%8E%E6%97%A5%E9%97%B4%E7%9A%84%E7%BD%91%E7%BB%9C%E5%85%B3%E7%B3%BB%E5%9B%A0%E5%AD%90/dlesc_clustering.py",
    "factor_pipeline.py": "https://raw.githubusercontent.com/hugo2046/QuantsPlaybook/master/B-%E5%9B%A0%E5%AD%90%E6%9E%84%E5%BB%BA%E7%B1%BB/%E5%9F%BA%E4%BA%8E%E9%9A%94%E5%A4%9C%E4%B8%8E%E6%97%A5%E9%97%B4%E7%9A%84%E7%BD%91%E7%BB%9C%E5%85%B3%E7%B3%BB%E5%9B%A0%E5%AD%90/factor_pipeline.py",
    "loade_factor.py": "https://raw.githubusercontent.com/hugo2046/QuantsPlaybook/master/B-%E5%9B%A0%E5%AD%90%E6%9E%84%E5%BB%BA%E7%B1%BB/%E5%9F%BA%E4%BA%8E%E9%9A%94%E5%A4%9C%E4%B8%8E%E6%97%A5%E9%97%B4%E7%9A%84%E7%BD%91%E7%BB%9C%E5%85%B3%E7%B3%BB%E5%9B%A0%E5%AD%90/loade_factor.py"
}

out_dir = Path(__file__).resolve().parent / "dlesc_ref"
out_dir.mkdir(parents=True, exist_ok=True)

for name, url in urls.items():
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read()
            with open(out_dir / name, "wb") as f:
                f.write(content)
        print(f"Saved {name} successfully.")
    except Exception as e:
        print(f"Error downloading {name}: {e}")
