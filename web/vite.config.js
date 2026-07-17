import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { Agent, ProxyAgent, fetch as fetchWithProxySupport } from 'undici';
import { resolveClientProxyUrl } from './server/clientProxy.js';

const webRoot = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(webRoot, '..');
const videoPath = join(projectRoot, 'assets', 'web', 'background_video', '1783750570912_clean_temporal_2x.mp4');
const databaseRoot = join(projectRoot, 'data', 'databases');
const subjectLabels = JSON.parse(readFileSync(join(projectRoot, 'configs', 'web_subject_labels.json'), 'utf8'));
const cacheRoot = join(projectRoot, 'tmp', 'web-paper-cache');
const tesseractRoot = join(webRoot, 'node_modules', 'tesseract.js');
const tesseractCoreRoot = join(webRoot, 'node_modules', 'tesseract.js-core');
const ocrLanguagePath = join(webRoot, 'node_modules', '@tesseract.js-data', 'eng', '4.0.0_best_int', 'eng.traineddata.gz');
const proxyUrl = resolveClientProxyUrl();
const paperDispatcher = proxyUrl ? new ProxyAgent(proxyUrl) : new Agent();
const tls12PaperDispatcher = proxyUrl
  ? new ProxyAgent({ uri: proxyUrl, requestTls: { maxVersion: 'TLSv1.2' } })
  : new Agent({ connect: { maxVersion: 'TLSv1.2' } });
const ocrCoreFiles = [
  'tesseract-core-lstm.wasm.js', 'tesseract-core-lstm.wasm',
  'tesseract-core-simd-lstm.wasm.js', 'tesseract-core-simd-lstm.wasm',
  'tesseract-core-relaxedsimd-lstm.wasm.js', 'tesseract-core-relaxedsimd-lstm.wasm',
];
const qualificationNames = subjectLabels.qualifications;
const examBoardNames = subjectLabels.exam_boards;
const courseNames = subjectLabels.courses;

function getSubjects() {
  if (!existsSync(databaseRoot)) return [];
  const subjects = [];
  for (const qualificationEntry of readdirSync(databaseRoot, { withFileTypes: true })) {
    if (!qualificationEntry.isDirectory()) continue;
    const qualification = qualificationEntry.name;
    const qualificationRoot = join(databaseRoot, qualification);
    for (const boardEntry of readdirSync(qualificationRoot, { withFileTypes: true })) {
      if (!boardEntry.isDirectory()) continue;
      const examBoard = boardEntry.name;
      const boardRoot = join(qualificationRoot, examBoard);
      for (const fileEntry of readdirSync(boardRoot, { withFileTypes: true })) {
        if (!fileEntry.isFile() || !fileEntry.name.endsWith('.sqlite')) continue;
        const prefix = `${examBoard}_${qualification}_`;
        if (!fileEntry.name.startsWith(prefix)) continue;
        const courseCode = fileEntry.name.slice(prefix.length, -'.sqlite'.length);
        const sourcePath = join(boardRoot, fileEntry.name);
        const sourceStat = statSync(sourcePath);
        subjects.push({
          id: `${qualification}:${examBoard}:${courseCode}`,
          qualification: {
            id: qualification,
            name: qualificationNames[qualification] || { zh: qualification, en: qualification },
          },
          examBoard: {
            id: examBoard,
            name: examBoardNames[examBoard] || { zh: examBoard.toUpperCase(), en: examBoard.toUpperCase() },
          },
          courseCode,
          name: courseNames[courseCode] || { zh: courseCode.toUpperCase(), en: courseCode.toUpperCase() },
          filename: fileEntry.name,
          databaseUrl: `/runtime/databases/${fileEntry.name}?v=${sourceStat.size}-${Math.trunc(sourceStat.mtimeMs)}`,
          sourcePath,
        });
      }
    }
  }
  return subjects.sort((left, right) => left.id.localeCompare(right.id));
}

function getPublicSubjects() {
  return getSubjects().map(({ sourcePath, ...subject }) => subject);
}

function sendFile(request, response, path, type) {
  const size = statSync(path).size;
  const range = request.headers.range;
  response.setHeader('Accept-Ranges', 'bytes');
  response.setHeader('Cache-Control', 'public, max-age=3600');
  response.setHeader('Content-Type', type);
  if (range) {
    const [startText, endText] = range.replace('bytes=', '').split('-');
    const start = Number(startText);
    const end = endText ? Number(endText) : size - 1;
    response.statusCode = 206;
    response.setHeader('Content-Range', `bytes ${start}-${end}/${size}`);
    response.setHeader('Content-Length', end - start + 1);
    createReadStream(path, { start, end }).pipe(response);
    return;
  }
  response.setHeader('Content-Length', size);
  createReadStream(path).pipe(response);
}

function runtimeMiddleware() {
  return async (request, response, next) => {
    const requestUrl = new URL(request.url, 'http://localhost');
    const pathname = requestUrl.pathname;
    if (pathname === '/runtime/subjects.json') {
      response.setHeader('Content-Type', 'application/json; charset=utf-8');
      response.end(JSON.stringify(getPublicSubjects()));
      return;
    }
    if (pathname === '/runtime/hero-video.mp4') {
      sendFile(request, response, videoPath, 'video/mp4');
      return;
    }
    if (pathname.startsWith('/runtime/databases/')) {
      const filename = basename(pathname);
      const subject = getSubjects().find((item) => item.filename === filename);
      if (!subject) { response.statusCode = 404; response.end(); return; }
      sendFile(request, response, subject.sourcePath, 'application/vnd.sqlite3');
      return;
    }
    if (pathname === '/runtime/ocr/worker.min.js') {
      sendFile(request, response, join(tesseractRoot, 'dist', 'worker.min.js'), 'text/javascript; charset=utf-8');
      return;
    }
    if (pathname === '/runtime/ocr/lang/eng.traineddata.gz') {
      sendFile(request, response, ocrLanguagePath, 'application/gzip');
      return;
    }
    if (pathname.startsWith('/runtime/ocr/core/')) {
      const filename = basename(pathname);
      if (!ocrCoreFiles.includes(filename)) { response.statusCode = 404; response.end(); return; }
      const type = filename.endsWith('.wasm') ? 'application/wasm' : 'text/javascript; charset=utf-8';
      sendFile(request, response, join(tesseractCoreRoot, filename), type);
      return;
    }
    if (pathname !== '/api/papers') { next(); return; }
    try {
      const sourceUrl = new URL(requestUrl.searchParams.get('url') || '');
      if (!['http:', 'https:'].includes(sourceUrl.protocol)) throw new Error('unsupported paper URL protocol');
      const cacheKey = createHash('sha256').update(sourceUrl.href).digest('hex');
      const cached = join(cacheRoot, `${cacheKey}.pdf`);
      if (!existsSync(cached)) {
        const upstream = await fetchWithProxySupport(sourceUrl, {
          dispatcher: sourceUrl.hostname === 'pmt.physicsandmathstutor.com'
            ? tls12PaperDispatcher
            : paperDispatcher,
          headers: { 'User-Agent': 'Oh-My-Exam/0.1 local question search' },
        });
        if (!upstream.ok) throw new Error(`paper provider returned ${upstream.status}`);
        const buffer = Buffer.from(await upstream.arrayBuffer());
        if (buffer.subarray(0, 4).toString() !== '%PDF') throw new Error('Paper provider response is not a PDF');
        mkdirSync(cacheRoot, { recursive: true });
        writeFileSync(cached, buffer);
      }
      sendFile(request, response, cached, 'application/pdf');
    } catch (error) {
      response.statusCode = 502;
      response.setHeader('Content-Type', 'application/json; charset=utf-8');
      response.end(JSON.stringify({ error: error.cause?.message || error.message }));
    }
  };
}

function runtimeAssets() {
  const installMiddleware = (server) => {
    server.middlewares.use(runtimeMiddleware());
  };
  return {
    name: 'oh-my-exam-runtime-assets',
    configureServer: installMiddleware,
    configurePreviewServer: installMiddleware,
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'runtime/hero-video.mp4', source: readFileSync(videoPath) });
      this.emitFile({ type: 'asset', fileName: 'runtime/ocr/worker.min.js', source: readFileSync(join(tesseractRoot, 'dist', 'worker.min.js')) });
      this.emitFile({ type: 'asset', fileName: 'runtime/ocr/lang/eng.traineddata.gz', source: readFileSync(ocrLanguagePath) });
      ocrCoreFiles.forEach((filename) => {
        this.emitFile({ type: 'asset', fileName: `runtime/ocr/core/${filename}`, source: readFileSync(join(tesseractCoreRoot, filename)) });
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), runtimeAssets()],
});
