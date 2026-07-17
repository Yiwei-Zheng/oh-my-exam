export function isMobileImageUploadDevice({
  navigatorObject = typeof navigator === 'undefined' ? undefined : navigator,
  matchMedia = typeof window === 'undefined' || !window.matchMedia ? undefined : window.matchMedia.bind(window),
} = {}) {
  const matches = (query) => Boolean(matchMedia?.(query)?.matches);

  return navigatorObject?.userAgentData?.mobile === true
    || matches('(max-width: 680px)')
    || (matches('(pointer: coarse)') && matches('(max-width: 1024px)'));
}
