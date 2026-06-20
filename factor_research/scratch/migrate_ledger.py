import json
from pathlib import Path

REGISTRY = Path("/Users/kiki/astcok/factor_research/strategy_versions.json")

def main():
    if not REGISTRY.exists():
        print("Registry file not found.")
        return

    data = json.loads(REGISTRY.read_text())
    
    # Define upgrades for each strategy family
    upgrades = {
        "small-cap-size": {
            "style_betas": {"size": 0.85, "volatility": 0.20, "value": -0.10},
            "capacity_m": 20.0,
            "failure_boundaries": {"max_drawdown": -0.35, "max_drawdown_days": 180}
        },
        "large-cap-growth-hedged": {
            "style_betas": {"size": -0.50, "growth": 0.60, "value": -0.40},
            "capacity_m": 150.0,
            "failure_boundaries": {"max_drawdown": -0.15, "max_drawdown_days": 120}
        },
        "industry-neglect-rotation": {
            "style_betas": {"size": 0.15, "value": 0.30, "crowdness": -0.60},
            "capacity_m": 80.0,
            "failure_boundaries": {"max_drawdown": -0.30, "max_drawdown_days": 150}
        },
        "hq-momentum-hedged": {
            "style_betas": {"momentum": 0.55, "quality": 0.45, "size": 0.10},
            "capacity_m": 100.0,
            "failure_boundaries": {"max_drawdown": -0.22, "max_drawdown_days": 120}
        },
        "d-le-sc-hedged": {
            "style_betas": {"size": -0.08, "momentum": -0.12, "idiosyncratic": 0.90},
            "capacity_m": 30.0,
            "failure_boundaries": {"max_drawdown": -0.30, "max_drawdown_days": 180}
        },
        "illiquidity": {
            "style_betas": {"size": 0.75, "illiquidity": 0.80, "volatility": 0.10},
            "capacity_m": 15.0,
            "failure_boundaries": {"max_drawdown": -0.30, "max_drawdown_days": 180}
        },
        "size-earnings": {
            "style_betas": {"size": 0.65, "quality": 0.40, "volatility": 0.15},
            "capacity_m": 25.0,
            "failure_boundaries": {"max_drawdown": -0.25, "max_drawdown_days": 150}
        },
        "size-low-vol": {
            "style_betas": {"size": 0.70, "volatility": -0.40, "value": 0.05},
            "capacity_m": 30.0,
            "failure_boundaries": {"max_drawdown": -0.25, "max_drawdown_days": 150}
        }
    }

    for fam in data.get("families", []):
        fam_id = fam.get("id")
        if fam_id in upgrades:
            fam.update(upgrades[fam_id])
            print(f"Upgraded family: {fam_id}")

    # Save data back sorted by id
    data["families"].sort(key=lambda f: f["id"])
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print("Migration complete and strategy_versions.json saved successfully!")

if __name__ == "__main__":
    main()
