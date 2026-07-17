import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { getSessionPaper } from './paperSession.js';
import { availablePaperSources, paperLocationUrl, resolvePostRenderCrop } from './cropGeometry.js';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

async function renderRegions(paper, regions) {
  if (!regions.length) return null;
  const pdf = await getDocument({ data: await paper.blob.arrayBuffer() }).promise;
  const segments = [];
  const renderedPages = new Map();
  try {
    for (const region of regions) {
      const scale = region.renderDpi / 72;
      const pageKey = `${region.pageIndex}:${region.renderDpi}`;
      let rendered = renderedPages.get(pageKey);
      if (!rendered) {
        const page = await pdf.getPage(region.pageIndex + 1);
        const viewport = page.getViewport({ scale });
        const canvas = document.createElement('canvas');
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
        rendered = { canvas, page };
        renderedPages.set(pageKey, rendered);
      }
      const rawLeft = Math.max(0, Math.round(region.x0 * scale));
      const rawTop = Math.max(0, Math.round(region.y0 * scale));
      const rawRight = Math.min(rendered.canvas.width, Math.round(region.x1 * scale));
      const rawBottom = Math.min(rendered.canvas.height, Math.round(region.y1 * scale));
      const crop = resolvePostRenderCrop(rawRight - rawLeft, rawBottom - rawTop, {
        left: region.postLeft,
        top: region.postTop,
        right: region.postRight,
        bottom: region.postBottom,
      });
      const canvas = document.createElement('canvas');
      canvas.width = crop.right - crop.left;
      canvas.height = crop.bottom - crop.top;
      canvas.getContext('2d').drawImage(
        rendered.canvas,
        rawLeft + crop.left,
        rawTop + crop.top,
        canvas.width,
        canvas.height,
        0,
        0,
        canvas.width,
        canvas.height,
      );
      segments.push({ canvas, gap: region.joinGap || 0 });
    }
  } finally {
    renderedPages.forEach(({ page }) => page.cleanup());
  }
  const output = document.createElement('canvas');
  output.width = Math.max(...segments.map(({ canvas }) => canvas.width));
  output.height = segments.reduce((height, segment) => height + segment.gap + segment.canvas.height, 0);
  const context = output.getContext('2d');
  context.fillStyle = '#fff';
  context.fillRect(0, 0, output.width, output.height);
  let top = 0;
  segments.forEach(({ canvas, gap }) => {
    top += gap;
    context.drawImage(canvas, 0, top);
    top += canvas.height;
  });
  await pdf.destroy();
  return output.toDataURL('image/png');
}

export async function renderQuestionPair(result, onProgress) {
  const questionRegions = result.crops.filter((crop) => crop.sourceType === 0);
  const answerRegions = result.crops.filter((crop) => crop.sourceType === 1);
  const sources = availablePaperSources(result);
  if (!sources.length) throw new Error('No source paper URL is available');
  const downloadProgress = new Map(sources.map(({ key }) => [key, 0]));
  const reportDownload = () => {
    const total = [...downloadProgress.values()].reduce((sum, value) => sum + value, 0);
    onProgress?.((total / sources.length) * 0.7);
  };
  const downloaded = await Promise.all(sources.map(async ({ key, url }) => [
    key,
    await getSessionPaper(url, (value) => { downloadProgress.set(key, value); reportDownload(); }),
  ]));
  const papers = Object.fromEntries(downloaded);
  onProgress?.(0.72);
  const [question, answer] = await Promise.all([
    papers.question ? renderRegions(papers.question, questionRegions) : null,
    papers.answer ? renderRegions(papers.answer, answerRegions) : null,
  ]);
  onProgress?.(1);
  return {
    question,
    answer,
    questionUrl: papers.question ? paperLocationUrl(result.paperUrl, questionRegions, 'question') : null,
    answerUrl: papers.answer ? paperLocationUrl(result.answerUrl, answerRegions, 'answer') : null,
  };
}
