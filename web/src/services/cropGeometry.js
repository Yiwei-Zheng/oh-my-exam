const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

export function resolvePostRenderCrop(width, height, crop) {
  if (!crop) return { left: 0, top: 0, right: width, bottom: height };
  const left = clamp(Number.isFinite(crop.left) ? crop.left : 0, 0, Math.max(0, width - 1));
  const top = clamp(Number.isFinite(crop.top) ? crop.top : 0, 0, Math.max(0, height - 1));
  const right = clamp(Number.isFinite(crop.right) ? crop.right : width, left + 1, width);
  const bottom = clamp(Number.isFinite(crop.bottom) ? crop.bottom : height, top + 1, height);
  return { left, top, right, bottom };
}

const finiteNumber = (value, fallback = 0) => (Number.isFinite(value) ? value : fallback);
const compactNumber = (value) => String(Math.round(value * 1000) / 1000);

export function resolvePaperLocation(region) {
  if (!region) return null;
  const renderScale = Math.max(1, finiteNumber(region.renderDpi, 72)) / 72;
  const sourceLeft = finiteNumber(region.x0);
  const sourceTop = finiteNumber(region.y0);
  const sourceRight = finiteNumber(region.x1, sourceLeft);
  const sourceBottom = finiteNumber(region.y1, sourceTop);
  const left = sourceLeft + (finiteNumber(region.postLeft) / renderScale);
  const top = sourceTop + (finiteNumber(region.postTop) / renderScale);
  const right = Number.isFinite(region.postRight)
    ? sourceLeft + (region.postRight / renderScale)
    : sourceRight;
  const bottom = Number.isFinite(region.postBottom)
    ? sourceTop + (region.postBottom / renderScale)
    : sourceBottom;
  return {
    pageNumber: Math.max(1, Math.trunc(finiteNumber(region.pageIndex)) + 1),
    left,
    top,
    right: Math.max(left + 1, right),
    bottom: Math.max(top + 1, bottom),
  };
}

export function paperLocationUrl(url, regions, kind = 'question') {
  const first = regions?.[0];
  if (!url || !first) return url;
  const location = resolvePaperLocation(first);
  const params = new URLSearchParams({
    source: url,
    kind,
    page: String(location.pageNumber),
    left: compactNumber(location.left),
    top: compactNumber(location.top),
    right: compactNumber(location.right),
    bottom: compactNumber(location.bottom),
  });
  return `#/source-pdf?${params.toString()}`;
}

export function parsePaperLocation(hash) {
  const prefix = '#/source-pdf?';
  if (!hash?.startsWith(prefix)) return null;
  const params = new URLSearchParams(hash.slice(prefix.length));
  const sourceUrl = params.get('source');
  if (!sourceUrl) return null;
  const pageNumber = Math.max(1, Math.trunc(Number(params.get('page'))) || 1);
  const left = Number(params.get('left'));
  const top = Number(params.get('top'));
  const right = Number(params.get('right'));
  const bottom = Number(params.get('bottom'));
  if (![left, top, right, bottom].every(Number.isFinite)) return null;
  return {
    sourceUrl,
    kind: params.get('kind') === 'answer' ? 'answer' : 'question',
    pageNumber,
    region: { left, top, right, bottom },
  };
}

export function availablePaperSources(result) {
  const crops = result.crops || [];
  return [
    { key: 'question', url: result.paperUrl, regions: crops.filter((crop) => crop.sourceType === 0) },
    { key: 'answer', url: result.answerUrl, regions: crops.filter((crop) => crop.sourceType === 1) },
  ].filter(({ url }) => url);
}
