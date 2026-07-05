# Design System

## Overview

Quant Research OS is a dark, high-density research cockpit for A-share factor research. The captured website uses a stable three-column desktop layout: left navigation, central evidence workspace, and a right AI audit panel. The visual identity is restrained and operational: black canvas, dark bordered panels, monospace evidence labels, and explicit status colors. The product tone is skeptical and audit-first, so blocked and pending states are shown as honest controls rather than failures to hide.

## Colors

- **Black Canvas**: `#000000` - full-frame base and negative space.
- **Sidebar Surface**: `#161617` - left and right persistent rails.
- **Primary Surface**: `#1C1C1E` - main cards and control panels.
- **Data Panel Surface**: `#0E2238` - blue-black cards for datasets, gates, and lake nodes.
- **Deep Panel Surface**: `#10263D` - nested data infrastructure blocks.
- **Border**: `#2C2C2E` - thin interface dividers.
- **Primary Text**: `#F5F5F7` - main copy.
- **Secondary Text**: `#8E8E93` - muted labels and explanatory text.
- **Evidence Text**: `#E6EDF7` - monospace metrics and system facts.
- **Brand Blue**: `#0A84FF` - active navigation, routes, and data flow arrows.
- **Pass Green**: `#30D158` - validated gates and clean checks.
- **Warn Amber**: `#FF9F0A` - caveats, unknown state, and review-required labels.
- **Fail Red**: `#FF453A` - blocked states, fail-closed banners, and leakage risks.
- **Purple Review**: `#BF5AF2` - human review / AI-assist traces.

## Typography

- **Primary Sans**: Apple system stack with generic sans fallback. Used for Chinese narration cards and interface copy.
- **Monospace**: SF Mono / ui-monospace. Used for data paths, APIs, guard IDs, hashes, and status labels.
- **Scale**: 76-96px for hero claims, 34-48px for beat titles, 20-28px for dense method labels, 16-18px for metadata.

## Elevation

Depth is created through dark surface contrast, thin borders, blue-green glows, and perspective-stacked UI panels. Shadows are soft and secondary; the main structure comes from bordered modules and moving data-flow lines. Screenshots should appear as framed product evidence, not decorative wallpaper.

## Components

- **Three-Column Quant Desk**: captured dashboard screenshot, framed and moved in 3D perspective.
- **Source Registry Grid**: source cards for Tushare, Tencent, Akshare, exchange, and Eastmoney-style feeds.
- **Data Lake Stack**: layered raw storage, compact layer, validation layer, and load API layer.
- **PIT Guard Board**: compact rules for `avail_date`, `shift(1)`, raw price valuation, and no legacy data.
- **Flow Spine**: animated blue path from source to lake to engine to web cockpit.
- **Fail-Closed Banner**: red evidence strip that refuses fake readiness.
- **Method Checklist**: final five-step method card that reads as an implementation recipe.

## Do's and Don'ts

### Do's

- Use exact status colors to distinguish pass, warning, blocked, and review states.
- Keep the interface dense, but make one dominant concept per beat.
- Use monospace for paths, APIs, guard names, dates, and manifests.
- Show blocked or pending states as evidence of honesty.
- Use the captured dashboard screenshot in multiple beats as product proof.

### Don'ts

- Do not imply AI or the dashboard can certify alpha validity.
- Do not market unverified strategy performance.
- Do not use generic fintech gradients or fake stock-chart optimism.
- Do not hide API failures; present fail-closed behavior as a control.
- Do not claim live data is loaded when the capture shows backend unavailable.
