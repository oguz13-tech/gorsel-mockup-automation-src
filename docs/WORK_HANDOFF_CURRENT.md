# PETEK brush hotfix checkpoint
Branch fix/petek-solid-brush-coverage, base PR27 ad0a0694a92cd70f8250cd5b7096448b13ee908c. Resolve latest remote HEAD for exact revision.
Implemented in GitHub Flask editor: source-resolution binary stroke rasterizer; interpolated segment coverage between pointer events; every touched paint pixel 255; convex quad containment; live double outline brush diameter/center and source-pixel size message. No renderer texture changes or old approved-mask rewrites.
Root causes observed in GitHub JS: independent antialiased canvas circles with no segment connection, no polygon clipping, no hover cursor. This is NOT evidence for the user's private Tk V3.8 symptom.
Tests: 3 Node behavioral cases PASS; JS syntax check PASS. Python regression result recorded in TEST_EVIDENCE. Windows/Ubuntu new CI pending, native Windows GUI screenshots not obtained.
Partial delivery: private Tk V3.8 not inspected/integrated; real before/after screenshots, safe protected-hole cleanup/QA, physical border option not implemented. Never blanket-close source holes: actual slots/arches cannot be distinguished from accidental gaps without reviewed protection/intent data. New interpolated strokes prevent gaps inside their geometric sweep but do not repair preexisting masks.
No user DB/source photos changed, no merge or live installation.
