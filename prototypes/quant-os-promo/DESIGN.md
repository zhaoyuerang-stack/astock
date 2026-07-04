# Design System

## Overview

Quant OS is a research-first finance interface with a high-density desktop workbench and a restrained personal-user audit surface. The product identity comes from the current web app: dark Apple-like surfaces for the professional cockpit, thin borders, system sans typography, monospace evidence labels, and explicit status colors. The mobile audit prototype adds a warmer paper surface for personal strategy review while preserving the same disciplined, non-recommendation tone.

## Colors

- **Black Canvas**: `#000000` - root video background and professional cockpit base.
- **Primary Surface**: `#1C1C1E` - dark cards and panels from the web app.
- **Secondary Surface**: `#161617` - sidebar and nested panels.
- **Border**: `#2C2C2E` - thin interface dividers.
- **Primary Text**: `#F5F5F7` - main dark-mode copy.
- **Secondary Text**: `#8E8E93` - muted metadata and labels.
- **Brand Blue**: `#0A84FF` - active nav, primary lockup, key evidence lines.
- **Pass Green**: `#30D158` - passed gates and safe states.
- **Warning Amber**: `#FF9F0A` - caution and holding state.
- **Fail Red**: `#FF453A` - blocked/falsified states.
- **Miniapp Paper**: `#F1EFE8` - personal audit phone surface.
- **Miniapp Ink**: `#2C2C2A` - warm dark text in the mobile prototype.
- **Miniapp Blue**: `#185FA5` - chat and CTA blue in the mobile prototype.

## Typography

- **Primary Sans**: Apple system stack / PingFang SC. Used for all Chinese product copy and interface labels.
- **Monospace**: SF Mono / ui-monospace. Used for strategy versions, gate IDs, hashes, and evidence labels.
- **Scale**: 80-96px for hero claims, 28-42px for explanatory product copy, 14-20px for dense UI metadata.

## Elevation

Depth is created with thin borders, dark surface contrast, subtle glows, and layered panels rather than heavy shadows. Dark cockpit scenes use `#1C1C1E` cards against `#000000`; the mobile scene uses a physical phone frame with a soft shadow on `#E1E8F0`.

## Components

- **Three-Column Quant Desk**: sidebar, central research workspace, right AI agent panel.
- **Gate Board**: nine compact audit cards with pass/warn/fail coloring.
- **Fail-Closed Verdict Stamp**: red evidence panel that says FALSIFIED or BLOCKED.
- **Personal Audit Phone**: WeChat-like strategy audit assistant with quota, disclaimer, chat, and report summary.
- **Single-Stock Decision Card**: holding-state split between "not yet bought" and "already holding."
- **Proof Strip**: compact capability cards for data lake, engine, 9-Gate, and single-stock entry.

## Do's and Don'ts

### Do's

- Use exact status colors to communicate pass, warning, and failure.
- Keep the product honest: show blocked/falsified states as a strength.
- Use monospace for evidence, gate IDs, and versioned system artifacts.
- Keep cards compact, bordered, and information-dense.

### Don'ts

- Do not present AI as an automatic trading oracle.
- Do not use generic fintech gradients or fake market hype.
- Do not hide the disclaimer; the product is a research and audit tool.
- Do not imply a strategy is deployable when the gates reject it.
