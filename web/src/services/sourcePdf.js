import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { getSessionPaper } from './paperSession.js';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

export async function createSourcePdfSession(sourceUrl, onProgress) {
  const paper = await getSessionPaper(sourceUrl, onProgress);
  const pdf = await getDocument({ data: await paper.blob.arrayBuffer() }).promise;
  let activeRender = null;

  return {
    pageCount: pdf.numPages,
    async renderPage(canvas, pageNumber, availableWidth) {
      activeRender?.cancel();
      const page = await pdf.getPage(clamp(pageNumber, 1, pdf.numPages));
      const baseViewport = page.getViewport({ scale: 1 });
      const scale = clamp(availableWidth / baseViewport.width, 0.5, 2);
      const pixelRatio = clamp(window.devicePixelRatio || 1, 1, 2);
      const viewport = page.getViewport({ scale });
      const outputViewport = page.getViewport({ scale: scale * pixelRatio });
      canvas.width = Math.ceil(outputViewport.width);
      canvas.height = Math.ceil(outputViewport.height);
      canvas.style.width = `${Math.ceil(viewport.width)}px`;
      canvas.style.height = `${Math.ceil(viewport.height)}px`;
      const renderTask = page.render({ canvasContext: canvas.getContext('2d'), viewport: outputViewport });
      activeRender = renderTask;
      try {
        await renderTask.promise;
      } finally {
        if (activeRender === renderTask) activeRender = null;
        page.cleanup();
      }
      return { width: viewport.width, height: viewport.height, scale };
    },
    destroy() {
      activeRender?.cancel();
      return pdf.destroy();
    },
  };
}
