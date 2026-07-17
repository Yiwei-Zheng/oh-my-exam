# Official Web

## Scope

`web/` owns the bilingual responsive website and the browser adapters needed for local question search.

## User flow

1. The landing page uses the project video as a responsive full-screen background, with synchronized soft and sharp layers creating a depth-of-field focus around the production line.
2. Its liquid-glass launcher expands into question-search and paper-building actions. Search enters through a full-screen loading transition; paper building currently routes to the explicit start placeholder.
3. No subject database is requested on initial load.
4. The search page mirrors the packer's cascading `qualification → exam_board → course` selection. Choosing the final subject loads only its SQLite package into a Web Worker through `sql.js` WASM.
5. Question images may come from the file picker, camera capture, or an image pasted from the clipboard while the upload zone is hovered or focused.
6. Tesseract WASM starts warming in the background after subject selection; the uploaded image is then cleaned and recognized locally.
7. Subject load builds a token posting index once. Searches shortlist candidates through that index before similarity ranking.
8. The selected result requests the stored source URLs through the same-origin paper proxy and keeps the returned PDFs in the current browser session as Blob URLs.
9. PDF.js renders stored `crop_regions`; opening a source paper enters the internal source-PDF route in the same tab, loads it through the same-origin proxy, opens the recorded page, scrolls to the final post-render crop, and highlights that exact question or answer region.
10. The search component remains mounted while the source-PDF route is open. Returning restores the same subject, uploaded image, OCR text, candidates, rendered question and answer, and search-page scroll position.

## Boundaries

- React components coordinate state and presentation; OCR, matching, database access, PDF cropping, and source-page rendering live in separate services.
- The client consumes portable packed databases and does not import Python processing code.
- Vite development and preview servers proxy and cache source PDFs under `tmp/web-paper-cache/` to avoid browser CORS limitations. They prefer an explicit `OH_MY_EXAM_PROXY`, then standard HTTP(S) proxy environment variables, and finally the enabled Windows per-user system proxy.
- Search feedback is one determinate percentage bar without stage descriptions.
- Hosted accounts, protected data, and automatic marking remain future API responsibilities.

## Runtime assets

`tools/sync_web_databases.py` validates `data/databases/**/*.sqlite`, copies current subject packages into the ignored `web/public/runtime/databases/` directory, removes stale copies, and atomically regenerates `subjects.json`. Development and production build commands run this sync automatically. Subject labels are configured in `configs/web_subject_labels.json`; generated runtime files are not source configuration.

The production build copies `assets/web/background_video/1783750570912_clean_temporal_2x.mp4` unchanged to `runtime/hero-video.mp4`, and includes the synchronized subject databases, SQLite WASM, PDF worker, and local English OCR runtime/model files. OCR and PDF modules are route/action split so the landing page does not load them.

## Verification

- `npm run build`
- Check 320 px, 375 px, tablet portrait/landscape, and desktop widths.
- Confirm `/runtime/subjects.json` lists only existing databases.
- Confirm database and video endpoints support range requests.
- Confirm `npm run dev` exposes a LAN URL and that clipboard image paste works from a focused or hovered upload zone.
- Test OCR and matching against a known processed question image.
