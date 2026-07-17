const papers = new Map();

async function downloadPaper(sourceUrl, onProgress) {
  if (!sourceUrl) throw new Error('Paper URL is missing from the subject database');
  const response = await fetch(`/api/papers?url=${encodeURIComponent(sourceUrl)}`);
  if (!response.ok || !response.headers.get('content-type')?.includes('pdf')) {
    throw new Error(`Paper request failed: ${response.status}`);
  }
  const total = Number(response.headers.get('content-length')) || 0;
  let blob;
  if (response.body && total) {
    const reader = response.body.getReader();
    const chunks = [];
    let received = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.byteLength;
      onProgress?.(Math.min(1, received / total));
    }
    blob = new Blob(chunks, { type: 'application/pdf' });
  } else {
    blob = await response.blob();
  }
  if (blob.size < 4) throw new Error('Paper response is empty');
  onProgress?.(1);
  return { blob, url: URL.createObjectURL(blob) };
}

export function getSessionPaper(sourceUrl, onProgress) {
  if (!papers.has(sourceUrl)) {
    const request = downloadPaper(sourceUrl, onProgress).catch((error) => {
      papers.delete(sourceUrl);
      throw error;
    });
    papers.set(sourceUrl, request);
  }
  else onProgress?.(1);
  return papers.get(sourceUrl);
}

export function clearPaperSession() {
  papers.forEach((paper) => paper.then(({ url }) => URL.revokeObjectURL(url)).catch(() => {}));
  papers.clear();
}
