import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { isLearningTrace, type LearningTrace } from "../../lib/trace-schema";
import {
  reduceReplay,
  initialState,
  comparisonEvents,
  type ReplayAction,
} from "../../lib/replay-state";
import ReplayControls from "./ReplayControls";
import EventTimeline from "./EventTimeline";
import CausalFlow from "./CausalFlow";
import TraceChart from "./TraceChart";
import ComparisonPanel from "./ComparisonPanel";
import FeasibleGrid from "./FeasibleGrid";
import TeachingScenes from "./TeachingScenes";
import { teachingText } from "../../lib/teaching-catalog";
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
  const element = useRef<HTMLDivElement>(null);
  const autoStarted = useRef(false);
  const [inView, setInView] = useState(false);
  const send = (action: ReplayAction) => {
    autoStarted.current = true;
    if (action.type === "PLAY" && !inView) {
      if (document.hidden) return;
      element.current?.querySelector("[data-motion-stage]")?.scrollIntoView({block: "center", behavior: "instant"});
      setInView(true);
    }
    dispatch(action);
  };
  const t = (key: string) => catalog[key] ?? key;
  useEffect(() => {
    if (!valid || !payloadValid) return;
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (navigation?.type === "back_forward") autoStarted.current = true;
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
      if (document.hidden) {
        autoStarted.current = true;
        dispatch({ type: "PAUSE" });
      }
    };
    document.addEventListener("visibilitychange", visibility);
    const pausePage = () => {
      autoStarted.current = true;
      dispatch({ type: "PAUSE" });
    };
    const restorePage = (event: PageTransitionEvent) => {
      if (event.persisted) pausePage();
    };
    window.addEventListener("pagehide", pausePage);
    window.addEventListener("pageshow", restorePage);
    return () => {
      cancelled = true;
      media.removeEventListener("change", motion);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", pausePage);
      window.removeEventListener("pageshow", restorePage);
    };
  }, [valid, payloadHash, traces]);
  useEffect(() => {
    if (!ready) return;
    const stage = element.current?.querySelector("[data-motion-stage]");
    if (!stage) return;
    if (typeof IntersectionObserver === "undefined") {
      autoStarted.current = true;
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(([entry]) => {
      const visible = entry.isIntersecting && entry.intersectionRatio >= 0.15;
      setInView(visible);
      if (!visible) dispatch({ type: "PAUSE" });
      else if (!autoStarted.current && !document.hidden &&
        !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        autoStarted.current = true;
        dispatch({ type: "PLAY" });
      }
    }, { threshold: [0, 0.15] });
    observer.observe(stage);
    return () => observer.disconnect();
  }, [ready]);
  useEffect(() => {
    if (!state.playing || state.reducedMotion || document.hidden || !inView) return;
    const last = index.get(state.presetId)!.events.length - 1;
    const timer = setTimeout(() => {
      dispatch({ type: "TICK" });
    }, (state.eventOrdinal === last ? 3200 : 2400) / state.speed);
    return () => clearTimeout(timer);
  }, [
    state.playing,
    state.reducedMotion,
    state.eventOrdinal,
    state.speed,
    state.presetId,
    inView,
  ]);
  if (!valid || !payloadValid)
    return <p role="alert">{t("learning.invalid")}</p>;
  const trace = index.get(state.presetId)!;
  const event = trace.events[state.eventOrdinal];
  return (
    <div
      className="learning-workbench"
      ref={element}
      lang={locale}
      data-ready={ready}
      data-manifest={manifestHash}
      data-current-event={event.event_id}
      data-playing={state.playing}
      data-in-view={inView}
      data-motion-allowed={ready && inView && !state.reducedMotion}
    >
      <ReplayControls
        state={state}
        traces={traces}
        ready={ready}
        t={t}
        dispatch={send}
      />
      <p className="replay-position" role="status" aria-live={state.playing ? "off" : "polite"}>
        {t("frame")} {state.eventOrdinal + 1} / {trace.events.length} ·{" "}
        {t("phase." + event.stage)}
      </p>

      <TeachingScenes
        trace={trace}
        traces={traces}
        event={event}
        locale={locale}
        ready={ready}
        label={t}
        select={(eventId) => send({ type: "SELECT_EVENT", eventId })}
        selectPath={(presetId,eventId) => send({ type: "SELECT_PATH_EVENT", presetId, eventId })}
      />
      <details className="teaching-evidence">
        <summary>{teachingText(locale, "evidence")}</summary>
        <EventTimeline
          events={trace.events}
          ordinal={state.eventOrdinal}
          ready={ready}
          t={t}
          select={(eventId) => send({ type: "SELECT_EVENT", eventId })}
          step={(type) => send({ type })}
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
                    checked={state.comparisonPresetIds.includes(
                      other.preset_id,
                    )}
                    onChange={(e) =>
                      send({
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
      </details>
    </div>
  );
}
