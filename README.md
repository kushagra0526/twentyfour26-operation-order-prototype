# cuttime: how much of a small CNC job is the order of operations?

twentyfour26's page says its software "picks the stock, setup, and tools, simulates the cut, and prices the job" and cuts in a San Francisco cell (https://twentyfour26.com/). Between cuts a cell spends time on tool changes and rapids, and both depend on the order of operations, not on the geometry. This prototype measures that on parametric 2.5D parts in a motion-planner time model. It is not their planner, and the time model is mine, not machine data.

## The setup
`cuttime/path.py`: pockets (zig-zag roughing in 2 mm passes, rounded finish contour), slots, peck-drilled holes and an outer profile become toolpaths; cutting time uses a GRBL-style look-ahead planner (junction speed from the corner angle, trapezoid velocity per segment, accel 500 mm/s2); rapids, drilling cycles and tool changes (12 s) are added around it. Tools: a 6 mm and a 3 mm end mill (chosen by the pocket's corner radius) and one drill per hole diameter. The outer profile always goes last.
`cuttime/order.py`: four orderings: the CAD tree order (a random listing of the features); group by tool; group by tool + nearest next feature; try every order of the tool groups, each with nearest-next ordering inside, and keep the fastest.

## Results (held-out: 60 parts with more small pockets, more slots, up to 15 holes and 6 drill sizes; fixed in git before the first completed run)
| | dev: job minutes | dev: tool changes | held-out: job minutes | held-out: tool changes | held-out time saved vs CAD order |
|---|---|---|---|---|---|
| CAD tree order | 4.91 | 8.6 | 6.25 | 13.0 | 0% |
| group by tool | 4.30 | 5.5 | 5.09 | 7.2 | 18.6% |
| group by tool + nearest next feature | 4.30 | 5.5 | 5.07 | 7.2 | 18.8% |
| best tool order (all permutations) + nearest next | 4.12 | 4.8 | 4.93 | 6.6 | **21.2%** |
Dev: 100 parts, saved 12.4 / 12.5 / 16.1%. No held-out part was slower than CAD order for any rule; plain grouping made 2 of 100 dev parts slower (it can put the profile's end mill group in the middle and change tools twice).
- Almost all of the saving is tool changes. The nearest-next-feature rule adds 0.2 points; rapids are cheap here. Cutting time does not depend on the order at all (a test checks this).
- What-if on the tool-change time (held-out, 30 parts, added after seeing the main result): at 3 s per change the best rule saves 8.5%, at 12 s 21.2%, at 30 s 32.0%. If the cell has an automatic tool changer that changes in a few seconds, this matters little; with manual or slow changes it is a third of the job.
- Not modelled: fixturing and re-setups, roughing-before-finishing across features, tool wear, chip evacuation, and anything that forces an order (a pocket that opens a hole, a thin web). The order search ignores those, so a real planner would need constraints.

## Read this before believing the table
The time model, tool-change time and part family are invented; the saving is measured inside the same model, so it is near-circular and shows an upper-bound style effect, not their machine. No claim about how their planner orders operations (I have not seen it).

## Run it (3 commands)
```
pip install numpy pytest
python -m pytest -q tests
python -m cuttime.run
```
numpy only. 5 tests; the full run takes several minutes (the permutation search).

Unofficial prototype by Kushagra Pratap Singh. Not affiliated with twentyfour26.
