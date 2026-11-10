import { useEffect } from 'react';

/** Элементы, за курсором над которыми следует мягкая подсветка (переменные --mx / --my). */
const SPOT = '.spot, .tile, .kpi, .card';

/**
 * Один слушатель на документ: обновляет координаты курсора только у элемента под ним
 * (раз в кадр), а у покинутого — сбрасывает. На сенсорных экранах не включается.
 */
export function useSpotlight() {
  useEffect(() => {
    if (typeof window === 'undefined' || window.matchMedia('(hover: none)').matches) return;
    let raf = 0;
    let target: Element | null = null;
    let x = 0;
    let y = 0;
    let last: HTMLElement | null = null;

    const apply = () => {
      raf = 0;
      const el = (target?.closest?.(SPOT) as HTMLElement | null) ?? null;
      if (last && last !== el) {
        last.style.removeProperty('--mx');
        last.style.removeProperty('--my');
      }
      last = el;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${Math.round(x - r.left)}px`);
      el.style.setProperty('--my', `${Math.round(y - r.top)}px`);
    };
    const onMove = (e: PointerEvent) => {
      target = e.target as Element;
      x = e.clientX;
      y = e.clientY;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    const onLeave = () => {
      target = null;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    document.addEventListener('pointermove', onMove, { passive: true });
    document.documentElement.addEventListener('pointerleave', onLeave);
    return () => {
      document.removeEventListener('pointermove', onMove);
      document.documentElement.removeEventListener('pointerleave', onLeave);
      cancelAnimationFrame(raf);
    };
  }, []);
}
