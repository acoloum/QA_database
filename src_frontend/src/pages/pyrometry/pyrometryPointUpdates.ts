import type { ItemRow } from './pyrometryFormUtils';
import { parseOptionalChannel } from './pyrometryFormUtils';
import type { SatPoint, SatReading, TusPoint } from '../../types';

export const updateTusPointAt = (
  points: TusPoint[],
  index: number,
  key: keyof TusPoint,
  value: string,
): TusPoint[] => points.map((point, currentIndex) =>
  currentIndex === index
    ? { ...point, [key]: key === '頻道' ? parseOptionalChannel(value) : value }
    : point,
);

export const updateSatFieldAt = (
  points: SatPoint[],
  index: number,
  key: keyof SatPoint,
  value: string,
): SatPoint[] => points.map((point, currentIndex) =>
  currentIndex === index
    ? { ...point, [key]: key === '頻道' ? parseOptionalChannel(value) : value }
    : point,
);

export const updateSatReadingAt = (
  points: SatPoint[],
  pointIndex: number,
  readingIndex: number,
  key: keyof SatReading,
  value: string,
): SatPoint[] => points.map((point, currentIndex) =>
  currentIndex === pointIndex
    ? {
        ...point,
        readings: point.readings.map((reading, currentReadingIndex) =>
          currentReadingIndex === readingIndex ? { ...reading, [key]: value } : reading,
        ),
      }
    : point,
);

export const updateItemRowAt = (
  rows: ItemRow[],
  index: number,
  key: keyof ItemRow,
  value: string,
): ItemRow[] => rows.map((row, currentIndex) => currentIndex === index ? { ...row, [key]: value } : row);
