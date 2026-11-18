import { useEffect, useRef, useState, type ReactNode } from "react";
import en from "../locales/event/en.json";
import zh from "../locales/event/zh-CN.json";
import "../styles/event-player.css";
export function eventText(locale: string) {
  return (key: string) =>
    (locale === "zh-CN" ? { ...en, ...zh } : en)[key as keyof typeof en] ?? key;
}
export default function StepPlayer({
  count,
  locale,
  render,
  auto = true,
  name,
}: {
  count: number;
  locale: string;
  render: (step: number, playing: boolean) => ReactNode;
  auto?: boolean;
  name: string;
}) {
  const t = eventText(locale),
    root = useRef<HTMLDivElement>(null),
    started = useRef(!auto);
  const [step, setStep] = useState(0),
    [playing, setPlaying] = useState(false),
    [ready, setReady] = useState(false),
    [reduced, setReduced] = useState(true),
    [visible, setVisible] = useState(false);
  useEffect(() => {
    setReady(true);
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const motion = () => {
      setReduced(media.matches);
      if (media.matches) {
        setPlaying(false);
        started.current = true;
      }
    };
    motion();
    media.addEventListener("change", motion);
    const hide = () => {
      if (document.hidden) {
        setPlaying(false);
        started.current = true;
      }
    };
    const away = () => {
      setPlaying(false);
      started.current = true;
    };
    document.addEventListener("visibilitychange", hide);
    window.addEventListener("pagehide", away);
    const observer = new IntersectionObserver(
      ([entry]) => {
        const inView = entry.isIntersecting && entry.intersectionRatio >= 0.2;
        setVisible(inView);
        if (!inView) setPlaying(false);
        else if (!started.current && !media.matches && !document.hidden) {
          started.current = true;
          setPlaying(true);
        }
      },
      { threshold: [0, 0.2] },
    );
    if (root.current) observer.observe(root.current);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", motion);
      document.removeEventListener("visibilitychange", hide);
      window.removeEventListener("pagehide", away);
    };
  }, []);
  useEffect(() => {
    if (!playing || reduced || !visible || document.hidden) return;
    const timer = setTimeout(
      () => setStep((s) => (s + 1) % count),
      step === count - 1 ? 3400 : 2600,
    );
    return () => clearTimeout(timer);
  }, [step, playing, count, reduced, visible]);
  const seek = (s: number) => {
    started.current = true;
    setPlaying(false);
    setStep(Math.max(0, Math.min(count - 1, s)));
  };
  return (
    <div
      className="step-player"
      data-step-player={name}
      data-step={step}
      data-playing={playing}
      data-step-ready={ready}
      ref={root}
    >
      <div className="event-visual" data-motion={playing && !reduced}>
        {render(step, playing && !reduced)}
      </div>
      <div className="step-transport" role="group" aria-label={t("controls")}>
        <button
          disabled={!ready}
          data-step-action="previous"
          onClick={() => seek(step - 1)}
          aria-label={t("previous")}
        >
          ◂ <span>{t("previous")}</span>
        </button>
        <button
          disabled={!ready || reduced}
          data-step-action="play"
          aria-pressed={playing}
          onClick={() => {
            started.current = true;
            setPlaying((p) => !p);
          }}
        >
          {playing ? "Ⅱ" : "▷"} <span>{t(playing ? "pause" : "play")}</span>
        </button>
        <button
          disabled={!ready}
          data-step-action="next"
          onClick={() => seek(step + 1)}
        >
          {t("next")} ▸
        </button>
        <button
          disabled={!ready}
          data-step-action="reset"
          onClick={() => seek(0)}
          aria-label={t("reset")}
        >
          ↶
        </button>
        <span className="step-counter" aria-live={playing ? "off" : "polite"}>
          {step + 1} / {count}
        </span>
      </div>
      {reduced && ready && <p className="event-note">{t("reduced")}</p>}
    </div>
  );
}
