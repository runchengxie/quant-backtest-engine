import type { ReplayState, ReplayAction } from "../../lib/replay-state";
import type { LearningTrace } from "../../lib/trace-schema";
export default function ReplayControls({
  state,
  traces,
  ready,
  t,
  dispatch,
}: {
  state: ReplayState;
  traces: LearningTrace[];
  ready: boolean;
  t: (k: string) => string;
  dispatch: (a: ReplayAction) => void;
}) {
  return (
    <fieldset disabled={!ready} className="learning-controls">
      <legend>{t("learning.controls")}</legend>
      <label>
        {t("scenario")}
        <select
          aria-label={t("scenario")}
          value={state.presetId}
          onChange={(e) =>
            dispatch({ type: "SELECT_PRESET", presetId: e.target.value })
          }
        >
          {traces.map((x) => (
            <option key={x.preset_id} value={x.preset_id}>
              {t("scenario." + x.preset_id)}
            </option>
          ))}
        </select>
      </label>
      <div className="replay-transport-slot"><div className="replay-transport">
      <button data-action="previous" title={t("learning.previous")} aria-label={t("learning.previous")} onClick={() => dispatch({ type: "PREVIOUS" })}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 5 7 12l10 7Z"/><path d="M5 5v14" fill="none"/></svg>
        <span>{t("learning.previous")}</span>
      </button>
      <button
        className="replay-toggle"
        data-action="play"
        aria-label={t(state.playing ? "pause" : "play")}
        aria-pressed={state.playing}
        disabled={state.reducedMotion}
        onClick={() => dispatch({ type: state.playing ? "PAUSE" : "PLAY" })}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">{state.playing ? <><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></> : <path d="m8 4 13 8-13 8Z"/>}</svg>
        <span>{t(state.playing ? "pause" : "play")}</span>
      </button>
      <button data-action="next" aria-label={t("step")} onClick={() => dispatch({ type: "NEXT" })}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 5 10 7-10 7Z"/><path d="M19 5v14" fill="none"/></svg>
        <span>{t("step")}</span>
      </button>
      <button data-action="reset" title={t("reset")} aria-label={t("reset")} onClick={() => dispatch({ type: "RESET" })}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 9a8 8 0 1 1 0 8M4 3v7h7" fill="none"/></svg>
        <span>{t("reset")}</span>
      </button>
      </div></div>
      <label>
        {t("learning.speed")}
        <select
          value={state.speed}
          onChange={(e) =>
            dispatch({
              type: "SET_SPEED",
              speed: Number(e.target.value) as 0.5 | 1 | 2,
            })
          }
        >
          <option>0.5</option>
          <option>1</option>
          <option>2</option>
        </select>
      </label>
      <label className="replay-scrubber">
        <span>{t("frame")} {state.eventOrdinal + 1} / {traces.find(x => x.preset_id === state.presetId)!.events.length}</span>
        <input type="range" min="0" max={traces.find(x => x.preset_id === state.presetId)!.events.length - 1}
          value={state.eventOrdinal} aria-label={t("learning.seek")}
          onChange={e => {
            const event = traces.find(x => x.preset_id === state.presetId)!.events[Number(e.currentTarget.value)];
            if (event) dispatch({type: "SELECT_EVENT", eventId: event.event_id});
          }} />
      </label>
      {state.reducedMotion && <p>{t("learning.reduced")}</p>}
    </fieldset>
  );
}
