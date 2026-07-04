# Storyboard

**Format:** 1920x1080  
**Audio:** Voiceover-ready; no rendered audio committed in this pass.  
**VO direction:** Calm senior operator, skeptical and precise. Leave pauses after each sentence.  
**Style basis:** DESIGN.md, WEB_DESIGN.md, current Next.js dashboard, and miniapp_v3_design.html.

## Asset Audit

| Asset | Type | Assign to Beat | Role |
| --- | --- | --- | --- |
| Current web dashboard UI | Reconstructed interface | Beat 1 | Three-column Quant OS cockpit and fail-closed operating state |
| 9-Gate governance model | Reconstructed interface | Beat 2 | Machine-audited pass/warn/fail proof board |
| miniapp_v3_design.html | Reconstructed phone UI | Beat 3 | Personal strategy audit assistant and disclaimer |
| Single-stock product framing | Reconstructed decision card | Beat 3 | Holding-vs-not-holding conservative decision split |
| Quant OS lockup | CSS brand element | Beat 4 | First/last brand signal |

## Beat 1 - Hook (0:00-0:05)

**VO:** "漂亮回测，不等于可以下手。"

**Concept:** Start inside the real cockpit, not a marketing hero. The system is already showing BLOCKED and defensive positioning, making the core promise clear: the product prevents over-trust before it creates action.

**Visual:** Dark Quant OS desktop. Left sidebar, central operations desk, and right AI agent panel assemble into view. A white NAV line draws across the chart while red and amber cards reveal blocked gates. The headline sits on the left: "漂亮回测 / 先假设有问题."

**Mood:** Skeptical, high-density, institutional.

**Animation:** Brand row rises in, headline slides from left, desk slides from right, cards cascade, chart line draws, agent messages rise.

**Transition:** Short opacity handoff into the audit board.

## Beat 2 - Audit (0:05-0:10)

**VO:** "Quant OS 把策略先送进九道门：数据、成本、样本外、D S R。"

**Concept:** The strategy moves through a mechanical trial. The viewer sees that the system is not asking the model for an opinion; it is enforcing a repeatable gate stack.

**Visual:** Nine gate cards assemble in a 3x3 grid. Pass cards are green, caution cards amber, failures red. The DSR gate and capacity gate lift slightly as the FALSIFIED stamp lands.

**Mood:** Compliance control room, fast but legible.

**Animation:** Left thesis fades up, gate cards cascade, a blue audit rail lights up, verdict stamp punches in, failed cards pulse once.

**Transition:** Fade and upward drift.

## Beat 3 - Personal Decision (0:10-0:15)

**VO:** "它不替你喊买卖，只告诉你：能不能信，哪里会翻车。"

**Concept:** Pull the institutional engine into a personal surface. The key is not a dashboard full of internal machinery; it is a conservative answer for a single stock or strategy.

**Visual:** A warm phone UI shows the strategy audit assistant and a FALSIFIED report. Beside it, a single-stock audit card splits the answer into "if you have not bought" and "if you already hold."

**Mood:** Practical, personal, cautious.

**Animation:** Phone rises with slight perspective, chat bubbles appear, report card snaps in, decision card enters from right, checklist items tick in.

**Transition:** Fade to brand close.

## Beat 4 - Close (0:15-0:20)

**VO:** "面向个人用户，从一只股票开始，把研究纪律变成日常决策。"

**Concept:** Resolve the product as a system of discipline, not a signal vending machine.

**Visual:** Quant OS lockup lands. Four proof cards show data lake, BacktestEngine, 9-Gate, and single-stock audit card. Final panel states: "先问能不能信，再问怎么行动。"

**Mood:** Calm, conclusive, restrained.

**Animation:** Logo lockup rises, proof cards cascade, final panel lands, blue mark breathes gently.

**Transition:** Hold on final frame.

## Production Architecture

```text
quant-os-promo/
├── index.html
├── DESIGN.md
├── SCRIPT.md
├── STORYBOARD.md
├── transcript.json
├── capture/
│   └── extracted/
│       ├── asset-descriptions.md
│       ├── tokens.json
│       └── visible-text.txt
└── compositions/
    ├── scene-1-hook.html
    ├── scene-2-audit.html
    ├── scene-3-decision.html
    └── scene-4-close.html
```
