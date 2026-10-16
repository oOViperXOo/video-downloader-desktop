# Quick add and combo-box fixes

- Replaced the Downloads search/filter row and modal add workflow with inline clipboard capture, Paste and Add.
- Inspected links go directly into the ready queue. Each item exposes media, quality, save format and connection choices before Start; Start all remains available.
- Combo popups show up to eight rows, scroll long lists, constrain geometry to the screen and elide long labels. Closed combos ignore wheel changes so scrolling the queue does not change download settings.
- Simple selection changes update the existing row instead of destroying the active control. Media changes rebuild after the selection event to populate dependent choices.
- Resolution/save-format changes clear an exact stream selection and stale size metadata. Audio mode clears video conversion and exposes MP3/M4A output.
- Inspection forwards the applied browser-cookie setting. Watch Later/liked lists give login guidance; playlist URLs are normalized and entries use individual video URLs.

Validation: full automated suite: 278 passed, 4 platform skips. Offscreen popup tests select item 50 of 70 using the mouse and check popup closure, geometry and dependent settings. Native Windows popup automation failed to keep the popup visible/select its target; interactive popup behavior remains unverified by that harness. No authenticated Watch Later access was attempted.
