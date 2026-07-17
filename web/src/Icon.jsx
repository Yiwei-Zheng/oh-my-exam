const paths = {
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" /></>,
  upload: <><path d="M12 16V4m-5 5 5-5 5 5" /><path d="M5 14v6h14v-6" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9" r="1.5" /><path d="m4 17 4.5-4 3.5 3 2.5-2 5.5 5" /></>,
  camera: <><path d="M4 8h3l1.5-2h7L17 8h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
  scan: <><path d="M4 9V4h5m6 0h5v5m0 6v5h-5M9 20H4v-5" /><path d="M7 12h10" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  external: <><path d="M14 4h6v6m0-6-9 9" /><path d="M18 13v7H4V6h7" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></>,
  document: <><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v5h5M10 12h5m-5 4h5" /></>,
  plus: <path d="M12 6v12M6 12h12" />,
};

export default function Icon({ name, size = 22 }) {
  return <svg aria-hidden="true" fill="none" height={size} viewBox="0 0 24 24" width={size}><g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">{paths[name]}</g></svg>;
}
