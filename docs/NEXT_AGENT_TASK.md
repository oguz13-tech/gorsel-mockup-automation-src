# Next task
Continue fix/petek-solid-brush-coverage. Read WORK_HANDOFF_CURRENT and issue24.
1. Obtain private latest Windows Tk package and source/mask/example pair through Library; do not publish it. Compare actual Tk pipeline before claiming the reported user defect fixed.
2. Verify live Flask canvas screenshot at zoom/size changes and pointer capture outside panel; Node tests cover rasterizer not browser rendering. Screenshot before/after still required.
3. Implement reviewed protected-region map + explicit paint-intent map for safe 1–2px hole cleanup; do not morphological-close an entire approved mask because real vents may be tiny. Add coverage QA and debug overlay before approval; never rewrite APPROVED.
4. Compare light-white render using exact user mask; texture/lighting separate from opacity. Add optional physical border only with known measurements and default off.
5. Continue Sprint2 B/C still open in PR27 handoff history: native multiprocess crash/recovery and naming matrix. Checkpoint all changes; no merge/live writes.
