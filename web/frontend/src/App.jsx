import { useEffect, useMemo, useRef, useState } from 'react';
import Icon from './Icon.jsx';
import { translations } from './content.js';
import { loadSubjectDatabase, prepareSubjectSearch, searchQuestions } from './services/databaseClient.js';
import { parsePaperLocation } from './services/cropGeometry.js';
import { isMobileImageUploadDevice } from './services/device.js';
import { clearPaperSession } from './services/paperSession.js';

const getRoute = () => {
  if (window.location.hash === '#/search') return 'search';
  if (window.location.hash === '#/start') return 'start';
  if (window.location.hash.startsWith('#/source-pdf?')) return 'sourcePdf';
  return 'home';
};

const getInitialLanguage = () => {
  const query = window.location.hash.split('?', 2)[1] || '';
  return new URLSearchParams(query).get('lang') === 'en' ? 'en' : 'zh';
};

const scheduleIdle = (callback) => {
  if ('requestIdleCallback' in window) {
    const handle = window.requestIdleCallback(callback, { timeout: 1800 });
    return () => window.cancelIdleCallback(handle);
  }
  const handle = window.setTimeout(callback, 300);
  return () => window.clearTimeout(handle);
};

function App() {
  const [language, setLanguage] = useState(getInitialLanguage);
  const [route, setRoute] = useState(getRoute);
  const [hasSearchSession, setHasSearchSession] = useState(() => getRoute() === 'search');
  const [transitionPhase, setTransitionPhase] = useState('idle');
  const transitionTimers = useRef([]);
  const previousRoute = useRef(route);
  const searchScrollPosition = useRef(0);
  const copy = translations[language];

  useEffect(() => {
    const onHashChange = () => setRoute(getRoute());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const previous = previousRoute.current;
    previousRoute.current = route;
    if (route === 'search') setHasSearchSession(true);
    else if (route !== 'sourcePdf') setHasSearchSession(false);
    if (route !== 'search' || previous !== 'sourcePdf') return undefined;
    const frame = requestAnimationFrame(() => window.scrollTo({ top: searchScrollPosition.current }));
    return () => cancelAnimationFrame(frame);
  }, [route]);

  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-Hans' : 'en';
    document.title = route === 'search' ? copy.search.documentTitle : route === 'start' ? copy.start.documentTitle : route === 'sourcePdf' ? copy.sourcePdf.documentTitle : copy.home.documentTitle;
    document.querySelector('meta[name="description"]')?.setAttribute('content', copy.metaDescription);
  }, [copy, language, route]);

  useEffect(() => {
    window.addEventListener('beforeunload', clearPaperSession);
    return () => window.removeEventListener('beforeunload', clearPaperSession);
  }, []);

  useEffect(() => () => transitionTimers.current.forEach(window.clearTimeout), []);

  const navigateToSearch = () => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      window.location.hash = '#/search';
      return;
    }
    transitionTimers.current.forEach(window.clearTimeout);
    setTransitionPhase('entering');
    transitionTimers.current = [
      window.setTimeout(() => { window.location.hash = '#/search'; }, 720),
      window.setTimeout(() => setTransitionPhase('leaving'), 860),
      window.setTimeout(() => setTransitionPhase('idle'), 1280),
    ];
  };

  return (
    <div className={`app app--${route}`}>
      <a className="skip-link" href="#main-content">{copy.skip}</a>
      <Header copy={copy} language={language} route={route} setLanguage={setLanguage} />
      {route === 'home' && <Home copy={copy} onSearch={navigateToSearch} />}
      {(route === 'search' || (route === 'sourcePdf' && hasSearchSession)) && (
        <SearchPage
          active={route === 'search'}
          copy={copy}
          language={language}
          onOpenSource={() => { searchScrollPosition.current = window.scrollY; }}
        />
      )}
      {route === 'start' && <StartPage copy={copy} />}
      {route === 'sourcePdf' && <SourcePdfPage copy={copy} hasSearchSession={hasSearchSession} />}
      <TransitionOverlay copy={copy} phase={transitionPhase} />
    </div>
  );
}

function Header({ copy, language, route, setLanguage }) {
  return (
    <header className="site-header">
      <a className="brand" href="#/" aria-label={copy.brand.homeLabel}>
        <span className="brand-mark" aria-hidden="true"><img src="/web-icon.png" alt="" /></span>
        <span>{copy.brand.name}</span>
      </a>
      <nav aria-label={copy.nav.label}>
        <a className={route === 'home' ? 'is-active' : ''} href="#/">{copy.nav.home}</a>
        <a className={['search', 'sourcePdf'].includes(route) ? 'is-active' : ''} href="#/search">{copy.nav.search}</a>
      </nav>
      <button className="language-button" type="button" onClick={() => setLanguage(language === 'zh' ? 'en' : 'zh')}>
        <Icon name="globe" size={18} />
        <span>{language === 'zh' ? 'EN' : '中文'}</span>
      </button>
    </header>
  );
}

function Home({ copy, onSearch }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const depthVideo = useRef(null);
  const focusVideo = useRef(null);

  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === 'Escape') setMenuOpen(false); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, []);

  const syncVideos = () => {
    const depth = depthVideo.current;
    const focus = focusVideo.current;
    if (!depth || !focus || depth.readyState < 2 || focus.readyState < 2) return;
    if (Math.abs(depth.currentTime - focus.currentTime) > .08) focus.currentTime = depth.currentTime;
    if (!depth.paused && focus.paused) focus.play().catch(() => {});
  };

  return (
    <main id="main-content" className="home">
      <video ref={depthVideo} className="home-video home-video--depth" autoPlay muted loop playsInline preload="metadata" aria-hidden="true" onPlaying={syncVideos} onTimeUpdate={syncVideos}>
        <source src="/runtime/hero-video.mp4" type="video/mp4" />
      </video>
      <video ref={focusVideo} className="home-video home-video--focus" autoPlay muted loop playsInline preload="metadata" aria-hidden="true" onLoadedData={syncVideos}>
        <source src="/runtime/hero-video.mp4" type="video/mp4" />
      </video>
      <div className="home-depth-haze" />
      <div className="home-scrim" />
      <section className="home-content" aria-labelledby="home-title">
        <h1 id="home-title">{copy.home.title}</h1>
        <p className="home-lead">{copy.home.lead}</p>
      </section>
      <div className={`launch-menu${menuOpen ? ' is-open' : ''}`}>
        <div className="launch-options" aria-hidden={!menuOpen}>
          <a className="launch-option launch-option--paper" href="#/start" tabIndex={menuOpen ? 0 : -1}>
            <Icon name="document" size={21} />
            <span><strong>{copy.home.paper}</strong><small>{copy.home.paperHint}</small></span>
          </a>
          <button className="launch-option launch-option--search" type="button" onClick={onSearch} tabIndex={menuOpen ? 0 : -1}>
            <Icon name="search" size={21} />
            <span><strong>{copy.home.search}</strong><small>{copy.home.searchHint}</small></span>
          </button>
        </div>
        <button className="launch-trigger" type="button" aria-expanded={menuOpen} aria-label={menuOpen ? copy.home.closeMenu : copy.home.openMenu} onClick={() => setMenuOpen((open) => !open)}>
          <span className="launch-ripple" aria-hidden="true"><i /><i /><i /></span>
          <Icon name="plus" size={24} />
        </button>
      </div>
      <footer className="home-footer">
        <span>{copy.home.footer}</span>
      </footer>
    </main>
  );
}

function TransitionOverlay({ copy, phase }) {
  if (phase === 'idle') return null;
  return (
    <div className={`page-transition is-${phase}`} role="status" aria-live="polite">
      <div className="transition-content">
        <p>{copy.home.transition}</p>
        <span className="loading-dots" aria-hidden="true"><i /><i /><i /></span>
      </div>
    </div>
  );
}

function StartPage({ copy }) {
  return (
    <main id="main-content" className="start-page">
      <section>
        <p className="eyebrow">START / PAPER BUILDER</p>
        <h1>{copy.start.title}</h1>
        <p>{copy.start.lead}</p>
        <a className="primary-button" href="#/">{copy.start.back}<Icon name="arrow" /></a>
      </section>
    </main>
  );
}

function SourcePdfPage({ copy, hasSearchSession }) {
  const location = useMemo(() => parsePaperLocation(window.location.hash), []);
  const [pageNumber, setPageNumber] = useState(location?.pageNumber || 1);
  const [pageCount, setPageCount] = useState(0);
  const [availableWidth, setAvailableWidth] = useState(0);
  const [viewport, setViewport] = useState(null);
  const [status, setStatus] = useState(location ? 'loading' : 'error');
  const session = useRef(null);
  const shell = useRef(null);
  const canvas = useRef(null);
  const highlight = useRef(null);

  useEffect(() => {
    if (!shell.current) return undefined;
    const updateWidth = () => setAvailableWidth(Math.max(280, shell.current.clientWidth - 32));
    updateWidth();
    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(updateWidth);
      observer.observe(shell.current);
      return () => observer.disconnect();
    }
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  useEffect(() => {
    if (!location) return undefined;
    let cancelled = false;
    setStatus('loading');
    import('./services/sourcePdf.js')
      .then(({ createSourcePdfSession }) => createSourcePdfSession(location.sourceUrl))
      .then((nextSession) => {
        if (cancelled) {
          nextSession.destroy();
          return;
        }
        session.current = nextSession;
        setPageCount(nextSession.pageCount);
        setPageNumber(Math.min(location.pageNumber, nextSession.pageCount));
      })
      .catch(() => { if (!cancelled) setStatus('error'); });
    return () => {
      cancelled = true;
      session.current?.destroy();
      session.current = null;
    };
  }, [location]);

  useEffect(() => {
    if (!session.current || !pageCount || !availableWidth || !canvas.current) return undefined;
    let cancelled = false;
    setStatus('loading');
    setViewport(null);
    session.current.renderPage(canvas.current, pageNumber, availableWidth)
      .then((nextViewport) => {
        if (cancelled) return;
        setViewport(nextViewport);
        setStatus('ready');
      })
      .catch((error) => {
        if (!cancelled && error?.name !== 'RenderingCancelledException') setStatus('error');
      });
    return () => { cancelled = true; };
  }, [availableWidth, pageCount, pageNumber]);

  useEffect(() => {
    if (status !== 'ready' || pageNumber !== location?.pageNumber || !highlight.current) return undefined;
    const frame = requestAnimationFrame(() => highlight.current?.scrollIntoView({ block: 'center', inline: 'center' }));
    return () => cancelAnimationFrame(frame);
  }, [location, pageNumber, status, viewport]);

  const showHighlight = location && viewport && pageNumber === location.pageNumber;
  const highlightStyle = showHighlight ? {
    left: `${location.region.left * viewport.scale}px`,
    top: `${location.region.top * viewport.scale}px`,
    width: `${Math.max(2, (location.region.right - location.region.left) * viewport.scale)}px`,
    height: `${Math.max(2, (location.region.bottom - location.region.top) * viewport.scale)}px`,
  } : undefined;
  const positionLabel = location?.kind === 'answer' ? copy.sourcePdf.answer : copy.sourcePdf.question;
  const returnToSearch = (event) => {
    if (!hasSearchSession) return;
    event.preventDefault();
    window.history.back();
  };

  return (
    <main id="main-content" className="source-pdf-page">
      <section className="source-pdf-heading">
        <p className="eyebrow">{copy.sourcePdf.eyebrow}</p>
        <h1>{copy.sourcePdf.title}</h1>
        <p>{positionLabel}</p>
      </section>
      <section ref={shell} className="source-pdf-shell" aria-label={copy.sourcePdf.title}>
        <div className="source-pdf-toolbar">
          <a href="#/search" onClick={returnToSearch}>{copy.sourcePdf.back}</a>
          <div>
            <button type="button" disabled={pageNumber <= 1 || status === 'loading'} onClick={() => setPageNumber((page) => page - 1)}>{copy.sourcePdf.previous}</button>
            <span>{copy.sourcePdf.page.replace('{page}', pageNumber).replace('{count}', pageCount || '—')}</span>
            <button type="button" disabled={!pageCount || pageNumber >= pageCount || status === 'loading'} onClick={() => setPageNumber((page) => page + 1)}>{copy.sourcePdf.next}</button>
          </div>
        </div>
        {status === 'error' ? (
          <p className="source-pdf-status" role="alert">{copy.sourcePdf.error}</p>
        ) : (
          <div className="source-pdf-document" aria-busy={status === 'loading'}>
            <div className="source-pdf-stage" style={viewport ? { width: `${viewport.width}px`, height: `${viewport.height}px` } : undefined}>
              <canvas ref={canvas} />
              {showHighlight && <span ref={highlight} className="source-pdf-highlight" style={highlightStyle} aria-label={positionLabel} />}
            </div>
            {status === 'loading' && <p className="source-pdf-status" role="status">{copy.sourcePdf.loading}</p>}
          </div>
        )}
      </section>
    </main>
  );
}

function SearchPage({ active, copy, language, onOpenSource }) {
  const [subjects, setSubjects] = useState([]);
  const [qualification, setQualification] = useState('');
  const [examBoard, setExamBoard] = useState('');
  const [subject, setSubject] = useState('');
  const [databaseState, setDatabaseState] = useState('idle');
  const [databaseInfo, setDatabaseInfo] = useState(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [ocrText, setOcrText] = useState('');
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('idle');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [renders, setRenders] = useState(null);
  const [error, setError] = useState('');
  const [sourcePickerOpen, setSourcePickerOpen] = useState(false);
  const galleryFileInput = useRef(null);
  const cameraFileInput = useRef(null);
  const sourceDialog = useRef(null);
  const uploadZone = useRef(null);
  const renderCache = useRef(new Map());
  const renderRequest = useRef(0);
  const cancelWarmup = useRef(() => {});

  useEffect(() => {
    fetch('/runtime/subjects.json')
      .then((response) => {
        if (!response.ok) throw new Error('subject manifest');
        return response.json();
      })
      .then(setSubjects)
      .catch(() => setError(copy.search.errors.subjects));
  }, [copy.search.errors.subjects]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => () => cancelWarmup.current(), []);
  useEffect(() => {
    if (!sourcePickerOpen) return undefined;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const focusFrame = requestAnimationFrame(() => sourceDialog.current?.querySelector('button')?.focus());
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setSourcePickerOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const buttons = [...(sourceDialog.current?.querySelectorAll('button') || [])];
      if (!buttons.length) return;
      const first = buttons[0];
      const last = buttons.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
      previousFocus?.focus?.({ preventScroll: true });
    };
  }, [sourcePickerOpen]);

  useEffect(() => {
    if (!active) setSourcePickerOpen(false);
  }, [active]);

  const qualifications = useMemo(() => {
    const unique = new Map();
    subjects.forEach((item) => unique.set(item.qualification.id, item.qualification));
    return [...unique.values()];
  }, [subjects]);
  const examBoards = useMemo(() => {
    const unique = new Map();
    subjects
      .filter((item) => item.qualification.id === qualification)
      .forEach((item) => unique.set(item.examBoard.id, item.examBoard));
    return [...unique.values()];
  }, [qualification, subjects]);
  const availableSubjects = useMemo(
    () => subjects.filter((item) => item.qualification.id === qualification && item.examBoard.id === examBoard),
    [examBoard, qualification, subjects],
  );
  const chosenSubject = useMemo(() => subjects.find((item) => item.id === subject), [subject, subjects]);

  const resetDatabase = () => {
    renderRequest.current += 1;
    renderCache.current.clear();
    cancelWarmup.current();
    setDatabaseInfo(null);
    setDatabaseState('idle');
    setResults([]);
    setSelected(null);
    setRenders(null);
    setError('');
  };

  const chooseQualification = (event) => {
    setQualification(event.target.value);
    setExamBoard('');
    setSubject('');
    resetDatabase();
  };

  const chooseExamBoard = (event) => {
    setExamBoard(event.target.value);
    setSubject('');
    resetDatabase();
  };

  const chooseSubject = async (event) => {
    const next = event.target.value;
    setSubject(next);
    resetDatabase();
    if (!next) return;
    const item = subjects.find((entry) => entry.id === next);
    setDatabaseState('loading');
    try {
      const info = await loadSubjectDatabase(item.databaseUrl);
      setDatabaseInfo(info);
      setDatabaseState('ready');
      prepareSubjectSearch().catch(() => {});
      cancelWarmup.current = scheduleIdle(() => {
        import('./services/ocr.js').then(({ warmupOcr }) => warmupOcr()).catch(() => {});
        import('./services/pdfCrop.js').catch(() => {});
      });
    } catch {
      setDatabaseState('error');
      setError(copy.search.errors.database);
    }
  };

  const selectFile = (next) => {
    if (!next) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(next);
    setPreviewUrl(URL.createObjectURL(next));
    setOcrText('');
    setResults([]);
    setSelected(null);
    setRenders(null);
    setError('');
    setStatus('idle');
    setProgress(0);
  };

  const chooseFile = (event) => {
    selectFile(event.target.files?.[0]);
    event.target.value = '';
  };

  const openUploadPicker = () => {
    if (isMobileImageUploadDevice()) {
      setSourcePickerOpen(true);
      return;
    }
    galleryFileInput.current?.click();
  };

  const chooseImageSource = (inputRef) => {
    const input = inputRef.current;
    if (!input) return;
    input.value = '';
    setSourcePickerOpen(false);
    input.click();
  };

  const pasteImage = (event) => {
    const item = [...(event.clipboardData?.items || [])].find((entry) => entry.type.startsWith('image/'));
    const pastedFile = item?.getAsFile();
    if (!pastedFile) return;
    event.preventDefault();
    const extension = pastedFile.type.split('/')[1]?.replace('jpeg', 'jpg') || 'png';
    const namedFile = new File([pastedFile], `clipboard-image.${extension}`, { type: pastedFile.type });
    selectFile(namedFile);
  };

  const runSearch = async () => {
    if (!file || databaseState !== 'ready') return;
    setError('');
    setResults([]);
    setSelected(null);
    setRenders(null);
    setStatus('ocr');
    setProgress(1);
    try {
      const { recognizeQuestion } = await import('./services/ocr.js');
      const recognized = await recognizeQuestion(file, (value) => setProgress(Math.max(2, 5 + (value * 65))));
      setOcrText(recognized.text);
      if (!recognized.text.trim()) throw new Error('empty ocr');
      setStatus('matching');
      setProgress(72);
      const matches = await searchQuestions(recognized.text, 5);
      setProgress(82);
      setResults(matches);
      if (!matches.length) {
        setStatus('noResults');
        return;
      }
      await showResult(matches[0]);
    } catch (reason) {
      setStatus('error');
      setError(reason?.message === 'empty ocr' ? copy.search.errors.ocrEmpty : copy.search.errors.search);
    }
  };

  const showResult = async (result) => {
    const requestId = ++renderRequest.current;
    setSelected(result);
    setError('');
    const cached = renderCache.current.get(result.id);
    if (cached) {
      setRenders(cached);
      setProgress(100);
      setStatus('done');
      return;
    }
    setRenders(null);
    setStatus('paper');
    setProgress((current) => Math.max(current, 82));
    try {
      const { renderQuestionPair } = await import('./services/pdfCrop.js');
      const images = await renderQuestionPair(result, (value) => {
        if (renderRequest.current === requestId) setProgress(82 + (value * 18));
      });
      renderCache.current.set(result.id, images);
      if (renderRequest.current !== requestId) return;
      setRenders(images);
      setProgress(100);
      setStatus('done');
    } catch {
      if (renderRequest.current !== requestId) return;
      setStatus('paperError');
      setError(copy.search.errors.paper);
    }
  };

  const busy = ['ocr', 'matching', 'paper'].includes(status);
  const subjectName = chosenSubject?.name?.[language] || chosenSubject?.name?.en;
  const localizedSourceUrl = (url) => url?.startsWith('#/source-pdf?') ? `${url}&lang=${language}` : url;

  return (
    <main id={active ? 'main-content' : undefined} className="search-page" hidden={!active}>
      <section className="search-intro">
        <p className="eyebrow">{copy.search.eyebrow}</p>
        <h1>{copy.search.title}</h1>
        <p>{copy.search.lead}</p>
      </section>

      <section className="search-workspace" aria-label={copy.search.workspaceLabel}>
        <div className="search-controls">
          <Step number="01" title={copy.search.subject.title} state={databaseState === 'ready' ? copy.search.ready : ''}>
            <div className="subject-selectors">
              <div>
                <label htmlFor="qualification">{copy.search.subject.qualificationLabel}</label>
                <select id="qualification" value={qualification} onChange={chooseQualification} disabled={databaseState === 'loading'} aria-describedby="subject-helper">
                  <option value="">{copy.search.subject.qualificationPlaceholder}</option>
                  {qualifications.map((item) => <option value={item.id} key={item.id}>{item.name[language] || item.name.en}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="exam-board">{copy.search.subject.examBoardLabel}</label>
                <select id="exam-board" value={examBoard} onChange={chooseExamBoard} disabled={!qualification || databaseState === 'loading'} aria-describedby="subject-helper">
                  <option value="">{copy.search.subject.examBoardPlaceholder}</option>
                  {examBoards.map((item) => <option value={item.id} key={item.id}>{item.name[language] || item.name.en}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="subject">{copy.search.subject.courseLabel}</label>
                <select id="subject" value={subject} onChange={chooseSubject} disabled={!examBoard || databaseState === 'loading'} aria-describedby="subject-helper">
                  <option value="">{copy.search.subject.coursePlaceholder}</option>
                  {availableSubjects.map((item) => <option value={item.id} key={item.id}>{item.name[language] || item.name.en}</option>)}
                </select>
              </div>
            </div>
            <p id="subject-helper" className="helper-text">
              {databaseState === 'loading' && copy.search.subject.loading}
              {databaseState === 'ready' && copy.search.subject.loaded.replace('{subject}', subjectName).replace('{count}', databaseInfo.questionCount.toLocaleString())}
              {databaseState === 'idle' && copy.search.subject.helper}
            </p>
          </Step>

          <Step number="02" title={copy.search.upload.title} state={file ? copy.search.ready : ''}>
            <input ref={galleryFileInput} className="sr-only" id="question-image" type="file" accept="image/*" tabIndex={-1} aria-hidden="true" onChange={chooseFile} />
            <input ref={cameraFileInput} className="sr-only" type="file" accept="image/*" capture="environment" tabIndex={-1} aria-hidden="true" onChange={chooseFile} />
            <button ref={uploadZone} className="upload-zone" type="button" aria-describedby="upload-helper" aria-haspopup={isMobileImageUploadDevice() ? 'dialog' : undefined} onClick={openUploadPicker} onMouseEnter={() => uploadZone.current?.focus({ preventScroll: true })} onPaste={pasteImage}>
              <Icon name="upload" size={26} />
              <strong>{file ? file.name : copy.search.upload.button}</strong>
              <span id="upload-helper">{copy.search.upload.helper}</span>
            </button>
            {previewUrl && <img className="upload-preview" src={previewUrl} alt={copy.search.upload.previewAlt} />}
          </Step>

          <button className="primary-button search-button" type="button" disabled={!file || databaseState !== 'ready' || busy} onClick={runSearch}>
            <Icon name="scan" />
            <span>{copy.search.submit}</span>
          </button>
          {busy && <Progress value={progress} />}
          {error && <p className="error-message" role="alert">{error}</p>}
        </div>

        <div className="search-results" aria-live="polite">
          {!selected && !busy && (
            <div className="empty-state">
              <Icon name="database" size={34} />
              <h2>{copy.search.empty.title}</h2>
              {copy.search.empty.body && <p>{copy.search.empty.body}</p>}
            </div>
          )}
          {results.length > 0 && (
            <div className="result-layout">
              <aside className="match-list" aria-label={copy.search.matchesLabel}>
                <p className="result-kicker">{copy.search.matches}</p>
                {results.map((result, index) => (
                  <button className={selected?.id === result.id ? 'is-selected' : ''} key={result.id} aria-pressed={selected?.id === result.id} onClick={() => showResult(result)} type="button">
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <strong>{result.paperStem} · {result.questionNumber}</strong>
                    <small>{Math.round(result.score * 100)}%</small>
                  </button>
                ))}
              </aside>
              <article className="result-detail" aria-busy={status === 'paper'}>
                <div className="result-header">
                  <div>
                    <p className="result-kicker">{copy.search.bestMatch}</p>
                    <h2>{selected.paperStem} · {selected.questionNumber}</h2>
                  </div>
                  <span>{Math.round(selected.score * 100)}% {copy.search.confidence}</span>
                </div>
                {ocrText && <details><summary>{copy.search.ocrText}</summary><p>{ocrText}</p></details>}
                <div className="paper-pair">
                  <PaperImage title={copy.search.question} image={renders?.question} empty={copy.search.noQuestionCrop} loading={status === 'paper'} loadingText={copy.search.loadingPaper} />
                  <PaperImage title={copy.search.answer} image={renders?.answer} empty={copy.search.noAnswerCrop} loading={status === 'paper'} loadingText={copy.search.loadingPaper} />
                </div>
                <div className="source-links">
                  {renders?.questionUrl && <a href={localizedSourceUrl(renders.questionUrl)} onClick={onOpenSource}>{copy.search.openQuestion}<Icon name="arrow" size={16} /></a>}
                  {renders?.answerUrl && <a href={localizedSourceUrl(renders.answerUrl)} onClick={onOpenSource}>{copy.search.openAnswer}<Icon name="arrow" size={16} /></a>}
                </div>
              </article>
            </div>
          )}
          {status === 'noResults' && <div className="empty-state"><h2>{copy.search.noResults.title}</h2><p>{copy.search.noResults.body}</p></div>}
        </div>
      </section>
      {sourcePickerOpen && (
        <div className="image-source-backdrop" onClick={(event) => { if (event.target === event.currentTarget) setSourcePickerOpen(false); }}>
          <section ref={sourceDialog} className="image-source-dialog" role="dialog" aria-modal="true" aria-labelledby="image-source-title" aria-describedby="image-source-description">
            <header>
              <p className="eyebrow">{copy.search.upload.sourceEyebrow}</p>
              <h2 id="image-source-title">{copy.search.upload.sourceTitle}</h2>
              <p id="image-source-description">{copy.search.upload.sourceDescription}</p>
            </header>
            <div className="image-source-options">
              <button type="button" onClick={() => chooseImageSource(galleryFileInput)}>
                <Icon name="image" size={24} />
                <span><strong>{copy.search.upload.gallery}</strong><small>{copy.search.upload.galleryHint}</small></span>
              </button>
              <button type="button" onClick={() => chooseImageSource(cameraFileInput)}>
                <Icon name="camera" size={24} />
                <span><strong>{copy.search.upload.camera}</strong><small>{copy.search.upload.cameraHint}</small></span>
              </button>
            </div>
            <button className="image-source-cancel" type="button" onClick={() => setSourcePickerOpen(false)}>{copy.search.upload.cancel}</button>
          </section>
        </div>
      )}
    </main>
  );
}

function Step({ number, title, state, children }) {
  return <section className="control-step"><div className="step-heading"><span>{number}</span><h2>{title}</h2>{state && <em><Icon name="check" size={15} />{state}</em>}</div>{children}</section>;
}

function Progress({ value }) {
  const percentage = Math.min(100, Math.max(0, Math.round(value)));
  return <div className="progress-block" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={percentage}><strong>{percentage}%</strong><div className="progress-track"><i style={{ transform: `scaleX(${percentage / 100})` }} /></div></div>;
}

function PaperImage({ title, image, empty, loading, loadingText }) {
  return <section><div className="paper-title"><span>{title}</span></div>{image ? <img src={image} alt={title} /> : <p className={`paper-empty${loading ? ' is-loading' : ''}`}>{loading ? loadingText : empty}</p>}</section>;
}

export default App;
