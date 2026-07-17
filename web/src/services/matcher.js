function normalize(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[ﬁﬂ]/g, (character) => (character === 'ﬁ' ? 'fi' : 'fl'))
    .toLowerCase()
    .replace(/[^a-z0-9+\-=<>π√^./ ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function tokenList(value) {
  return [...new Set(value.split(' ').filter((token) => token.length > 1))];
}

function bigrams(value) {
  const compact = value.replace(/\s/g, '');
  const result = new Set();
  for (let index = 0; index < compact.length - 1; index += 1) result.add(compact.slice(index, index + 2));
  return result;
}

function prepare(value) {
  const normalized = normalize(value);
  return { normalized, tokens: new Set(tokenList(normalized)), bigrams: bigrams(normalized) };
}

function overlap(left, right) {
  if (!left.size || !right.size) return 0;
  let common = 0;
  left.forEach((item) => { if (right.has(item)) common += 1; });
  return (2 * common) / (left.size + right.size);
}

function preparedSimilarity(query, candidate) {
  const tokenScore = overlap(query.tokens, candidate.tokens);
  const characterScore = overlap(query.bigrams, candidate.bigrams);
  const lengthRatio = Math.min(query.normalized.length, candidate.normalized.length)
    / Math.max(query.normalized.length, candidate.normalized.length, 1);
  return (tokenScore * 0.58) + (characterScore * 0.34) + (lengthRatio * 0.08);
}

export function similarity(query, candidate) {
  return preparedSimilarity(prepare(query), prepare(candidate));
}

export function createSearchIndex(questions) {
  const preparedQuestions = questions.map((question) => ({ question, prepared: prepare(question.content) }));
  const postings = new Map();
  preparedQuestions.forEach(({ prepared }, index) => {
    prepared.tokens.forEach((token) => {
      const matches = postings.get(token);
      if (matches) matches.push(index);
      else postings.set(token, [index]);
    });
  });
  return { preparedQuestions, postings };
}

export function searchIndex(index, queryText, limit) {
  const query = prepare(queryText);
  const hitCounts = new Map();
  const maximumPostingSize = Math.max(80, Math.floor(index.preparedQuestions.length * 0.18));
  query.tokens.forEach((token) => {
    const matches = index.postings.get(token);
    if (!matches || matches.length > maximumPostingSize) return;
    matches.forEach((questionIndex) => hitCounts.set(questionIndex, (hitCounts.get(questionIndex) || 0) + 1));
  });
  const candidates = hitCounts.size
    ? [...hitCounts.entries()].sort((left, right) => right[1] - left[1]).slice(0, 700).map(([questionIndex]) => questionIndex)
    : index.preparedQuestions.map((_, questionIndex) => questionIndex);
  return candidates
    .map((questionIndex) => {
      const entry = index.preparedQuestions[questionIndex];
      return { ...entry.question, score: preparedSimilarity(query, entry.prepared) };
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, limit)
    .filter((question) => question.score >= 0.08);
}

export function rankMatches(questions, query, limit) {
  return searchIndex(createSearchIndex(questions), query, limit);
}
