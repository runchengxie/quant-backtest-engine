import StepPlayer, { eventText } from "./StepPlayer";
export default function FrameworkAnimation({ locale }: { locale: string }) {
  const t = eventText(locale);
  return (
    <StepPlayer
      name="framework"
      locale={locale}
      count={5}
      render={(step) => (
        <figure className="framework-animation" data-feedback={step === 4}>
          <ol className="framework-track">
            {["market", "plan", "execute", "account"].map((id, i) => (
              <li key={id} data-active={step === i}>
                <span className="framework-node">{i + 1}</span>
                <span>{t("flow." + id)}</span>
              </li>
            ))}
          </ol>
          <div
            className="framework-signal"
            aria-hidden="true"
            style={{ left: (step === 4 ? 1 : step) * 25 + 12.5 + "%" }}
          />
          <div className="framework-return" data-active={step === 4}>
            <span aria-hidden="true">↶</span> {t("flow.feedback")}
          </div>
          <p className="framework-step-note" aria-live="off">
            {t("flow.detail." + step)}
          </p>
        </figure>
      )}
    />
  );
}
