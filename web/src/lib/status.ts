import type { ComparisonStatus, TopicStatus } from '../api/types';

export type Tone = 'critical' | 'warning' | 'good' | 'neutral' | 'serious' | 'info';

export const TOPIC_STATUS: Record<TopicStatus, { tone: Tone; label: string; icon: string }> = {
  requires_attention: { tone: 'critical', label: 'Требует внимания', icon: '!' },
  needs_practice: { tone: 'warning', label: 'Нужно закрепление', icon: '~' },
  mastered: { tone: 'good', label: 'Освоено', icon: '✓' },
  insufficient_data: { tone: 'neutral', label: 'Мало данных', icon: '?' },
  no_data: { tone: 'neutral', label: 'Нет данных', icon: '–' },
  mixed_versions: { tone: 'serious', label: 'Разные версии', icon: '≠' },
};

export const STATUS_ORDER: TopicStatus[] = [
  'requires_attention',
  'needs_practice',
  'mastered',
  'insufficient_data',
  'mixed_versions',
  'no_data',
];

export const COMPARISON_STATUS: Record<ComparisonStatus, { tone: Tone; label: string; hint: string }> = {
  comparable: {
    tone: 'good',
    label: 'Сопоставимо',
    hint: 'Достаточно пар в обеих группах, одна версия теста и близкий стартовый уровень.',
  },
  insufficient_data: {
    tone: 'neutral',
    label: 'Мало данных',
    hint: 'Нужно не меньше 10 учеников с парой «до/после» в каждой группе.',
  },
  not_comparable: {
    tone: 'serious',
    label: 'Несопоставимо',
    hint: 'Группы нельзя честно сравнить: разные версии/шкалы или большой стартовый разрыв.',
  },
};
