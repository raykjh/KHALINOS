# Signal Board Atelier

A highly polished, responsive browser-based decision board styled as a private strategy atelier. It allows small teams to input options, score them from 1 to 5 across customizable criteria, view a deterministic leader, and persist data locally.

## Visual Design & Architecture
- **The Triptych Layout**: A modular, three-panel architectural layout inspired by drafting boards and folding triptych planning screens.
- **Visual Palette**: Warm parchment background (`#FDFBF7`), deep charcoal ink text (`#1C1A17`), and muted brass accents (`#A38A5E`).
- **Typography**: Classical serif headers paired with ultra-clean geometric sans-serif for inputs and labels.
- **Tactile Depth**: Avoids generic SaaS dashboard tropes. Employs hard, crisp 1px offsets, fine brass-ruled borders, and smooth transitions.

## Features
1. **Appraisal Criteria & Entry**: Customize criteria names on the fly. Inscribe new options with custom descriptions and initial scores.
2. **The Option Ledger**: View active options as dense vertical cards. Adjust scores dynamically with brass stud controls.
3. **The Monolith**: Instantly highlights the current leading option with real-time score distribution charts.
4. **Persistence**: Fully offline-ready with LocalStorage state preservation.

## How to Run and Use
1. Open `index.html` in any modern web browser.
2. Use the **Appraisal Criteria & Entry** panel to define your evaluation criteria (e.g., Impact, Feasibility, Alignment).
3. Fill out the **Record New Option** form to add a strategic path. Click **Inscribe Option** to save it.
4. Adjust scores dynamically on each option card using the tactile 1-5 rating buttons (studs).
5. Observe **The Monolith** panel to see the current leader and comparative standing chart update in real-time.
6. To clear all data, click **Purge Atelier Ledger** and confirm the prompt.
