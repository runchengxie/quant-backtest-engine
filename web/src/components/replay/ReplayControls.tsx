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
      <button onClick={() => dispatch({ type: "PREVIOUS" })}>
        {t("learning.previous")}
      </button>
      <button onClick={() => dispatch({ type: "NEXT" })}>{t("step")}</button>
      <button onClick={() => dispatch({ type: "RESET" })}>{t("reset")}</button>
      <button
        disabled={state.reducedMotion}
        onClick={() => dispatch({ type: state.playing ? "PAUSE" : "PLAY" })}
      >
        {t(state.playing ? "pause" : "play")}
      </button>
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
      {state.reducedMotion && <p>{t("learning.reduced")}</p>}
    </fieldset>
  );
}
