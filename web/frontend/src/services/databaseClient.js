let worker;
let sequence = 0;
const pending = new Map();

function getWorker() {
  if (worker) return worker;
  worker = new Worker(new URL('../workers/database.worker.js', import.meta.url), { type: 'module' });
  worker.onmessage = ({ data }) => {
    const request = pending.get(data.id);
    if (!request) return;
    pending.delete(data.id);
    if (data.error) request.reject(new Error(data.error));
    else request.resolve(data.payload);
  };
  worker.onerror = (event) => {
    pending.forEach(({ reject }) => reject(new Error(event.message)));
    pending.clear();
  };
  return worker;
}

function request(type, payload = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    getWorker().postMessage({ id, type, payload });
  });
}

export const loadSubjectDatabase = (databaseUrl) => request('load', { databaseUrl });
export const prepareSubjectSearch = () => request('prepare');
export const searchQuestions = (text, limit = 5) => request('search', { text, limit });
