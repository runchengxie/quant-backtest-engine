import type { LearningTrace } from "./trace-schema.ts";
export type ReplayState = {
  presetId: string;
  eventOrdinal: number;
  playing: boolean;
  speed: 0.5 | 1 | 2;
  comparisonPresetIds: string[];
  reducedMotion: boolean;
};
export type ReplayAction =
  | { type: "SELECT_PRESET"; presetId: string }
  | { type: "SELECT_EVENT"; eventId: string }
  | { type: "NEXT" | "PREVIOUS" | "RESET" | "PLAY" | "PAUSE" }
  | { type: "SET_SPEED"; speed: 0.5 | 1 | 2 }
  | { type: "SET_COMPARISON"; presetIds: string[] }
  | { type: "SET_REDUCED_MOTION"; value: boolean };
export function initialState(presetId: string): ReplayState {
  return {
    presetId,
    eventOrdinal: 0,
    playing: false,
    speed: 1,
    comparisonPresetIds: [],
    reducedMotion: false,
  };
}
export function reduceReplay(
  state: ReplayState,
  action: ReplayAction,
  index: ReadonlyMap<string, LearningTrace>,
): ReplayState {
  const trace = index.get(state.presetId);
  if (!trace) throw new Error("unknown selected preset");
  const last = trace.events.length - 1;
  switch (action.type) {
    case "SELECT_PRESET":
      return index.has(action.presetId)
        ? {
            ...state,
            presetId: action.presetId,
            eventOrdinal: 0,
            playing: false,
            comparisonPresetIds: [],
          }
        : state;
    case "SELECT_EVENT": {
      const n = trace.events.findIndex((e) => e.event_id === action.eventId);
      return n < 0 ? state : { ...state, eventOrdinal: n, playing: false };
    }
    case "NEXT":
      return {
        ...state,
        eventOrdinal: Math.min(last, state.eventOrdinal + 1),
        playing: false,
      };
    case "PREVIOUS":
      return {
        ...state,
        eventOrdinal: Math.max(0, state.eventOrdinal - 1),
        playing: false,
      };
    case "RESET":
      return { ...state, eventOrdinal: 0, playing: false };
    case "PLAY":
      return state.reducedMotion || state.eventOrdinal === last
        ? state
        : { ...state, playing: true };
    case "PAUSE":
      return { ...state, playing: false };
    case "SET_SPEED":
      return [0.5, 1, 2].includes(action.speed)
        ? { ...state, speed: action.speed }
        : state;
    case "SET_COMPARISON":
      return {
        ...state,
        comparisonPresetIds: [
          ...new Set(
            action.presetIds.filter(
              (id) => index.has(id) && id !== state.presetId,
            ),
          ),
        ],
        eventOrdinal: 0,
        playing: false,
      };
    case "SET_REDUCED_MOTION":
      return {
        ...state,
        reducedMotion: action.value,
        playing: action.value ? false : state.playing,
      };
  }
}
export function comparisonEvents(
  state: ReplayState,
  index: ReadonlyMap<string, LearningTrace>,
) {
  const trace = index.get(state.presetId)!;
  const point = trace.comparison?.points.find(
    (p) => p.id === trace.events[state.eventOrdinal]?.event_id,
  );
  return state.comparisonPresetIds.map((id) => {
    const own = index.get(id)!;
    const eventId = point?.events[id];
    return {
      trace: own,
      event: eventId
        ? (own.events.find((e) => e.event_id === eventId) ?? null)
        : null,
    };
  });
}
