Key things to test carefully now that we made some Optimizations/Big changes,
2026-04-16


### Food Scoring (behavioral change)

The `_execute_move` food pickup fix means creatures now score food they walk onto via explore/memory replay — not just adjacent-food override. This **changes simulation behavior**. You'll see:

- Higher `food_consumed` totals than before
- Higher creature scores, which affects reproduction selection
- Potentially different learning dynamics since `recent_steps` is no longer cleared on these pickups (it is cleared in the adjacent-food path)

Watch for creatures accumulating score faster than expected, or the graph showing food depleting much quicker.

### Dirty-Rect Rendering Artifacts

- If you see stale tiles (old creature positions not clearing, ghost food), it means a `set_tile` call isn't going through the tracked path, or `take_changed_cells()` is being called at the wrong time
- **Epoch reset** and **sim reset** are the riskiest moments — lots of cells change at once. Verify the grid fully repaints after those
- Clicking a creature to select it should still highlight correctly (selection change doesn't go through `refresh_dirty`)

### Graph Reset on Epoch Boundary

- The history clears each epoch (`self.history = []`), so the graph resets. If you run many epochs, make sure the graph doesn't accumulate stale data or flicker on reset
- With very fast tick intervals (<30ms), pyqtgraph `setData` every tick could lag — watch for the UI feeling sluggish at high speed

### Settings Validation Edge Case

- The validation `return`s early without creating a simulation. If the app starts with invalid saved settings, `self.simulation` stays `None` and buttons won't work. You'd need to fix settings then hit Reset Sim.

### `filter_empty_steps` Change

- Previously: kept only data after the last all-empty step
- Now: removes all empty steps but keeps everything else

This means creatures may now create memories from sequences that were previously discarded. Could lead to more memories being stored — watch memory counts in the details window.

### `World.get_tile()` No Longer Raises

- Any code that was catching `ValueError` from `get_tile()` for boundary detection now silently gets `Tile.WALL`. This should be fine (no callers were relying on the exception), but if you ever add boundary-sensitive logic, keep it in mind.