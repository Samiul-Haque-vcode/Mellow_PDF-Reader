# Interactive Windows release validation

Automated tests and packaged smoke checks do not establish behavior on physical
Windows devices. Use a development build on Windows 10 and 11 and record the app
version, commit/build artifact, OS version, display scales and device/driver.
No physical-device results have been recorded by the Linux development host.

| Area | Procedure and expected result |
| --- | --- |
| Caption tabs | Enable Settings → Appearance → Tabs in the Windows title bar, save and restart. Click/close/switch crowded tabs and use +. Caption buttons stay clear at narrow widths and 100%, 125%, 150% and 200% scaling. Turn the setting off and restart to restore the standard title bar. |
| Windows behavior | Minimize using the caption button, Alt+Space → Minimize and taskbar; restore each from the taskbar in normal and maximized modes. The window stays minimized, restores its prior size, and has one clear tab/caption row with working buttons and unchanged split locations. Repeat with crowded tabs and each theme. Drag empty caption space; double-click maximize/restore; drag down from maximized; resize all borders; use Win+arrows. On Windows 11 hover Maximize for Snap Layouts. Record any difference from the standard caption. |
| Fullscreen | In a split, enter/exit fullscreen repeatedly, reveal/hide controls and type in search. No caption buttons remain over the PDF in fullscreen. Both panes retain their source location, zoom and focus. |
| Physical gestures | Try mouse Ctrl+wheel and touchpad pinch/scroll with each pane focused. The source point stays under the pointer while zooming. Ordinary scrolling does not zoom, and momentum does not skip repeated single-page/spread turns. |
| Mixed DPI | Move/resize normal and maximized windows between differently scaled monitors, including a screen left of the primary. Disconnect the secondary, then reopen the session. The window remains visible and each pane retains its PDF source location where scroll limits allow. |
| Accessibility | Use keyboard-only tab/toolbar navigation, Windows Narrator and high-contrast mode. Check focused tab/file names, page entry, search status, Settings and temporary destination panels. Record inaccessible controls rather than assuming Qt's defaults suffice. |
| Real PDFs | Exercise large textbooks, mathematical diagrams, transparency, scanned/image-heavy pages, unusual dimensions and outlines. Check facing-cover alignment, all rotations, text search/copy, internal previews and independent split zoom. Scans have no OCR and equations are not converted to LaTeX. |
| Tools and files | Preview/extract/merge/convert images, cancel large work, retry and save. Existing destinations and source hashes remain unchanged after cancellation/error. Exercise moved files, Locate File, encrypted reader PDFs and unsupported encrypted utility inputs. |
| Distribution | Install/uninstall and run the portable build on a clean Windows user profile without Python. Verify Open with, unchanged default application, bundled notices and actual signatures/hashes. Record SmartScreen separately from Defender detections. |

When manually requested with artifact uploads enabled, CI adds `Windows-caption-verification` with normal/narrow/maximized render
captures and `CAPTION.json`, using Qt's Windows platform rather than offscreen.
Those checks are narrower than this interactive matrix. A signing script is not
evidence that a build was signed; consult that build's `SECURITY.json`.
