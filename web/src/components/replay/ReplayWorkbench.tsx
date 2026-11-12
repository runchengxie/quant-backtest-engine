import { useEffect, useMemo, useReducer, useState } from "react";
import { isLearningTrace, type LearningTrace } from "../../lib/trace-schema";
import {
  reduceReplay,
  initialState,
  comparisonEvents,
} from "../../lib/replay-state";
import ReplayControls from "./ReplayControls";
import EventTimeline from "./EventTimeline";
import CausalFlow from "./CausalFlow";
import TraceChart from "./TraceChart";
import ComparisonPanel from "./ComparisonPanel";
import FeasibleGrid from "./FeasibleGrid";
export default function ReplayWorkbench({
  traces,
  catalog,
  manifestHash,
  payloadHash,
  locale,
}: {
  traces: LearningTrace[];
  catalog: Record<string, string>;
  manifestHash: string;
  payloadHash: string;
  locale: string;
}) {
  const valid =
    traces.length > 0 &&
    traces.every(isLearningTrace) &&
    /^[0-9a-f]{64}$/.test(manifestHash);
  const index = useMemo(
    () => new Map(traces.map((t) => [t.preset_id, t])),
    [traces],
  );
  const [state, dispatch] = useReducer(
    (
      s: ReturnType<typeof initialState>,
      a: Parameters<typeof reduceReplay>[1],
    ) => reduceReplay(s, a, index),
    initialState(traces[0]?.preset_id ?? ""),
  );
  const [ready, setReady] = useState(false);
  const [payloadValid, setPayloadValid] = useState(true);
  const t = (key: string) => catalog[key] ?? key;
  useEffect(() => {
    if (!valid || !payloadValid) return;
    let cancelled = false;
    crypto.subtle
      .digest("SHA-256", new TextEncoder().encode(JSON.stringify(traces)))
      .then((bytes) => {
        if (cancelled) return;
        const actual = Array.from(new Uint8Array(bytes), (v) =>
          v.toString(16).padStart(2, "0"),
        ).join("");
        setPayloadValid(actual === payloadHash);
        setReady(actual === payloadHash);
      })
      .catch(() => {
        if (!cancelled) setPayloadValid(false);
      });
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const motion = () =>
      dispatch({ type: "SET_REDUCED_MOTION", value: media.matches });
    motion();
    media.addEventListener("change", motion);
    const visibility = () => {
      if (document.hidden) dispatch({ type: "PAUSE" });
    };
    document.addEventListener("visibilitychange", visibility);
    const pausePage = () => dispatch({ type: "PAUSE" });
    window.addEventListener("pagehide", pausePage);
    window.addEventListener("pageshow", pausePage);
    return () => {
      cancelled = true;
      media.removeEventListener("change", motion);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", pausePage);
      window.removeEventListener("pageshow", pausePage);
    };
  }, [valid, payloadHash, traces]);
  useEffect(() => {
    if (!state.playing || state.reducedMotion || document.hidden) return;
    const timer = setTimeout(() => {
      dispatch({ type: "NEXT" });
      dispatch({ type: "PLAY" });
    }, 1000 / state.speed);
    return () => clearTimeout(timer);
  }, [
    state.playing,
    state.reducedMotion,
    state.eventOrdinal,
    state.speed,
    state.presetId,
  ]);
  if (!valid || !payloadValid)
    return <p role="alert">{t("learning.invalid")}</p>;
  const trace = index.get(state.presetId)!;
  const event = trace.events[state.eventOrdinal];
  return (
    <div
      className="learning-workbench"
      lang={locale}
      data-ready={ready}
      data-manifest={manifestHash}
      data-current-event={event.event_id}
    >
      <ReplayControls
        state={state}
        traces={traces}
        ready={ready}
        t={t}
        dispatch={dispatch}
      />
      <p role="status" aria-live="polite">
        {t("frame")} {state.eventOrdinal + 1} / {trace.events.length} ·{" "}
        {t("phase." + event.stage)}
      </p>
      <EventTimeline
        events={trace.events}
        ordinal={state.eventOrdinal}
        ready={ready}
        t={t}
        select={(eventId) => dispatch({ type: "SELECT_EVENT", eventId })}
        step={(type) => dispatch({ type })}
      />
      <CausalFlow event={event} t={t} />
      <TraceChart event={event} events={trace.events} t={t} />
      <FeasibleGrid trace={trace} t={t} />
      {trace.comparison && (
        <fieldset disabled={!ready}>
          <legend>{t("learning.comparison")}</legend>
          {traces
            .filter((x) => x.preset_id !== trace.preset_id)
            .map((other) => (
              <label key={other.preset_id}>
                <input
                  type="checkbox"
                  checked={state.comparisonPresetIds.includes(other.preset_id)}
                  onChange={(e) =>
                    dispatch({
                      type: "SET_COMPARISON",
                      presetIds: e.target.checked
                        ? [...state.comparisonPresetIds, other.preset_id]
                        : state.comparisonPresetIds.filter(
                            (id) => id !== other.preset_id,
                          ),
                    })
                  }
                />
                {t("scenario." + other.preset_id)}
              </label>
            ))}
        </fieldset>
      )}
      <ComparisonPanel rows={comparisonEvents(state, index)} t={t} />
    </div>
  );
}
