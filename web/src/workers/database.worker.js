import initSqlJs from 'sql.js';
import sqlWasmUrl from 'sql.js/dist/sql-wasm.wasm?url';
import { createSearchIndex, searchIndex as findMatches } from '../services/matcher.js';

let database;
let questions = [];
let searchIndex;
let databaseInfo;

function rows(statement) {
  const result = [];
  while (statement.step()) result.push(statement.getAsObject());
  statement.free();
  return result;
}

function cropsFor(questionId) {
  const statement = database.prepare(`
    SELECT source_type AS sourceType, region_order AS regionOrder, page_index AS pageIndex,
      x0, y0, x1, y1, COALESCE(render_dpi, 150) AS renderDpi,
      join_gap_px AS joinGap, post_left AS postLeft, post_top AS postTop,
      post_right AS postRight, post_bottom AS postBottom
    FROM crop_regions WHERE question_id = ? ORDER BY source_type, region_order
  `);
  statement.bind([questionId]);
  return rows(statement);
}

async function load(databaseUrl) {
  database?.close();
  database = undefined;
  databaseInfo = undefined;
  questions = [];
  searchIndex = undefined;
  const [SQL, response] = await Promise.all([
    initSqlJs({ locateFile: () => sqlWasmUrl }),
    fetch(databaseUrl),
  ]);
  if (!response.ok) throw new Error(`Database request failed: ${response.status}`);
  database = new SQL.Database(new Uint8Array(await response.arrayBuffer()));
  const info = rows(database.prepare('SELECT qualification, exam_board AS examBoard, course_code AS courseCode, course_display_name AS courseDisplayName FROM database_info LIMIT 1'))[0];
  questions = rows(database.prepare(`
    SELECT q.id, q.local_question_key AS localKey, q.question_number AS questionNumber,
      p.qp_stem AS paperStem, p.ms_stem AS answerStem,
      p.qp_url AS paperUrl, p.ms_url AS answerUrl, t.content
    FROM question_texts t
    JOIN questions q ON q.id = t.question_id
    JOIN papers p ON p.id = q.paper_id
    WHERE length(trim(t.content)) > 8
  `));
  databaseInfo = { ...info, questionCount: questions.length };
  return databaseInfo;
}

function prepare() {
  if (!database) throw new Error('No subject database loaded');
  if (!searchIndex) searchIndex = createSearchIndex(questions);
  return { questionCount: databaseInfo.questionCount };
}

function search(text, limit) {
  if (!database) throw new Error('No subject database loaded');
  prepare();
  const matches = findMatches(searchIndex, text, limit)
    .map((question) => ({
      ...question,
      crops: cropsFor(question.id),
    }));
  return matches;
}

self.onmessage = async ({ data }) => {
  try {
    let payload;
    if (data.type === 'load') payload = await load(data.payload.databaseUrl);
    else if (data.type === 'prepare') payload = prepare();
    else payload = search(data.payload.text, data.payload.limit);
    self.postMessage({ id: data.id, payload });
  } catch (error) {
    self.postMessage({ id: data.id, error: error.message });
  }
};
