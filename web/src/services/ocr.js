import { createWorker, PSM } from 'tesseract.js';

let workerPromise;
let progressCallback;

function prepareWorker() {
  if (!workerPromise) {
    workerPromise = createWorker('eng', 1, {
      workerPath: '/runtime/ocr/worker.min.js',
      corePath: '/runtime/ocr/core',
      langPath: '/runtime/ocr/lang',
      logger: (message) => {
        if (message.status === 'recognizing text') progressCallback?.(message.progress || 0);
      },
    }).then(async (worker) => {
      await worker.setParameters({
        tessedit_pageseg_mode: PSM.AUTO,
        preserve_interword_spaces: '1',
      });
      return worker;
    });
  }
  return workerPromise;
}

async function preprocess(file) {
  const bitmap = await createImageBitmap(file);
  const maximum = 2200;
  const scale = Math.min(1, maximum / Math.max(bitmap.width, bitmap.height));
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);
  const canvas = typeof OffscreenCanvas === 'undefined' ? document.createElement('canvas') : new OffscreenCanvas(width, height);
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const image = context.getImageData(0, 0, canvas.width, canvas.height);
  const data = image.data;
  for (let index = 0; index < data.length; index += 4) {
    const luminance = (data[index] * 0.299) + (data[index + 1] * 0.587) + (data[index + 2] * 0.114);
    const value = luminance < 178 ? 0 : 255;
    data[index] = value;
    data[index + 1] = value;
    data[index + 2] = value;
  }
  context.putImageData(image, 0, 0);
  if ('convertToBlob' in canvas) return canvas.convertToBlob({ type: 'image/png' });
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
}

export async function recognizeQuestion(file, onProgress) {
  progressCallback = onProgress;
  try {
    onProgress?.(0.02);
    const [worker, image] = await Promise.all([prepareWorker(), preprocess(file)]);
    onProgress?.(0.08);
    const { data } = await worker.recognize(image);
    onProgress?.(1);
    return { text: data.text.replace(/\s+/g, ' ').trim(), confidence: data.confidence };
  } finally {
    progressCallback = undefined;
  }
}

export function warmupOcr() {
  return prepareWorker();
}
