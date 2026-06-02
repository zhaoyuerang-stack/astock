"""
策略版本登记 —— 两层结构：母策略(family) → 版本(version)

核心理念：具体策略默认会失效，真正要管理的是「母策略生命周期」。
  · 母策略(family)：一个独立 alpha 家族，记 核心假设 / 适用市场 / 失效信号 / status
  · 版本(version)：该家族下的参数与数据口径变体，记 配置 / 绩效 / status / 备注
  · 数据口径(data_full/data_lake) 是版本属性，不再占版本号语义（防"喂出来的高收益"被当真）

版本 status 约定：候选 / 在册 / 退役 / 参考
母策略 status 约定：active / paused / retired

用法：
  python3 strategy_registry.py                      # 打印母策略分组对比表
  from strategy_registry import register_family, register
  register_family("momentum", "截面动量", hypothesis=..., regime=..., decay_signal=...)
  register("momentum", "v1.0", desc, config, data_scope, metrics, status="候选", notes=...)
"""
import json
from pathlib import Path
from datetime import date

REGISTRY = Path(__file__).parent / "strategy_versions.json"


def _load():
    if not REGISTRY.exists():
        return {"families": []}
    data = json.loads(REGISTRY.read_text())
    if isinstance(data, list):        # 旧扁平格式 → 视为空，由 __main__ 重建
        return {"families": []}
    return data


def _save(data):
    data["families"].sort(key=lambda f: f["id"])
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def register_family(id, name, hypothesis="", regime="", decay_signal="", status="active"):
    """登记/更新一个母策略（同 id 覆盖元信息，保留其下版本）"""
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == id), None)
    if fam is None:
        fam = {"id": id, "versions": []}
        data["families"].append(fam)
    fam.update(name=name, hypothesis=hypothesis, regime=regime,
               decay_signal=decay_signal, status=status)
    _save(data)
    return id


def register(family, version, desc, config, data_scope, metrics, status="候选", notes=""):
    """登记/更新某母策略下的一个版本（同 family+version 覆盖）"""
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记，请先 register_family('{family}', ...)")
    fam["versions"] = [v for v in fam["versions"] if v["version"] != version]   # 同号覆盖
    fam["versions"].append({
        "version": version, "date": str(date.today()), "desc": desc,
        "config": config, "data_scope": data_scope, "metrics": metrics,
        "status": status, "notes": notes,
    })
    fam["versions"].sort(key=lambda v: v["version"])
    _save(data)
    return f"{family}/{version}"


def show():
    """按母策略分组打印台账"""
    data = _load()
    if not data["families"]:
        print("暂无登记母策略"); return
    for fam in data["families"]:
        print(f"\n■ 母策略 {fam['id']}（{fam.get('name','')}）  status={fam.get('status','')}")
        for k, label in (("hypothesis", "假设"), ("regime", "适用"), ("decay_signal", "失效信号")):
            if fam.get(k):
                print(f"    {label}：{fam[k]}")
        print(f"  {'版本':<6}{'数据口径':<26}{'年化':>8}{'回撤':>8}{'夏普':>6}{'达标':>5}{'状态':>6}  备注")
        print("  " + "-" * 100)
        for v in fam["versions"]:
            m, ds = v["metrics"], v["data_scope"]
            scope = f"{ds['source']}·{ds['period']}{'·幸存者偏差' if ds.get('survivorship_bias') else ''}"
            print(f"  {v['version']:<6}{scope:<26}{m['annual']:>7.1%}{m['maxdd']:>8.1%}"
                  f"{m['sharpe']:>6.2f}{'✅' if m['hit'] else '❌':>5}{v.get('status',''):>6}  {v['notes']}")


# ── 重建现有台账（v1/v2/v2.1 归入 small-cap-size 母策略）──
if __name__ == "__main__":
    import os; os.chdir(Path(__file__).parent)

    register_family(
        "small-cap-size", "小盘成交额因子",
        hypothesis="小盘流动性溢价 / size 因子（-log 60日均成交额，选小盘）",
        regime="小盘占优市；小盘等权指数 > MA16 时持仓，否则空仓",
        decay_signal="小盘等权指数滚动跑输沪深300 / size 因子 IC 转负（定量阈值待定）",
        status="active")

    register("small-cap-size", "v1.0", "原始达标策略（小盘60+小盘指数MA16择时+1.25x杠杆）",
             config={"factor": "size60(-log成交额60均)", "timing": "小盘指数MA16",
                     "top_n": 25, "rebal_days": 20, "leverage": 1.25},
             data_scope={"source": "data_full", "period": "2018-2026", "survivorship_bias": True},
             metrics={"annual": 0.404, "maxdd": -0.146, "sharpe": 2.06, "calmar": 2.77, "hit": True},
             status="参考",
             notes="❌含幸存者偏差水分(active过滤剔退市股)，高估约8.5%")

    register("small-cap-size", "v2.0", "v1.0迁移到data_lake准确数据（同配置，无幸存者偏差）",
             config={"factor": "size60", "timing": "小盘指数MA16",
                     "top_n": 25, "rebal_days": 20, "leverage": 1.25},
             data_scope={"source": "data_lake", "period": "2018-2026", "survivorship_bias": False},
             metrics={"annual": 0.3192, "maxdd": -0.1189, "sharpe": 1.82, "calmar": 2.68, "hit": False},
             status="在册",
             notes="✅真实基线：去水分后年化32%，夏普卡玛仍优秀，但未达35%目标")

    register("small-cap-size", "v2.1", "v2.0全历史压力测试（含2015股灾/2017小盘崩盘）",
             config={"factor": "size60", "timing": "小盘指数MA16",
                     "top_n": 25, "rebal_days": 20, "leverage": 1.25},
             data_scope={"source": "data_lake", "period": "2010-2026", "survivorship_bias": False},
             metrics={"annual": 0.3396, "maxdd": -0.2195, "sharpe": 1.63, "calmar": 1.55, "hit": False},
             status="参考",
             notes="2017+9%(择时扛住)✅；2015+389%已核查为真实小盘疯牛(月度符合历史/0极端单日/小盘指数+109%/持仓真实暴涨)，回撤22%可信")

    print("已重建母策略两层台账：\n")
    show()
