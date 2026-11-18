import { useState } from "react";
import evidence from "../data/queue-demo.json";
import StepPlayer, { eventText } from "./StepPlayer";
export default function QueueDemo({ locale }: { locale: string }) {
  const t = eventText(locale),
    [preset, setPreset] = useState<keyof typeof evidence.cases>("timely"),
    [changed, setChanged] = useState(false);
  const data = evidence.cases[preset];
  return (
    <section className="queue-demo" aria-label={t("queue.title")}>
      <h2>{t("queue.title")}</h2>
      <p>{t("queue.intro")}</p>
      <label className="event-preset">
        {t("scenario")}{" "}
        <select
          value={preset}
          onChange={(e) => {
            setChanged(true);
            setPreset(e.target.value as keyof typeof evidence.cases);
          }}
        >
          {Object.keys(evidence.cases).map((id) => (
            <option key={id} value={id}>
              {t(id)}
            </option>
          ))}
        </select>
      </label>
      <StepPlayer
        key={preset}
        name="queue"
        locale={locale}
        count={data.events.length}
        auto={!changed}
        render={(step) => {
          const event = data.events[step],
            command = data.commands[step],
            report = data.reports.find((r) => r.event_id === event.event_id)!;
          return (
            <div className="queue-frame" data-queue-event={event.event_id}>
              <div className="command-heading">
                <span>
                  {t("queue.event")} · {t(event.order_id)}
                </span>
                <strong>{t("status." + event.status)}</strong>
              </div>
              <ol className="command-clocks">
                {[
                  ["send", command.send_ns],
                  ["arrival", String(event.effective_ns)],
                  ["response", report.delivered_ns],
                ].map(([label, value]) => (
                  <li key={label}>
                    <small>{t(label)}</small>
                    <strong data-clock={label}>{value} ns</strong>
                  </li>
                ))}
              </ol>
              <p className="event-note">{t("queue.order")}</p>
              <div className="queue-sides">
                {(
                  [
                    ["bids", event.bids, 1],
                    ["asks", event.asks, -1],
                  ] as const
                ).map(([side, levels, direction]) => (
                  <section key={side} className="queue-side">
                    <h3>{t(side)}</h3>
                    <small>{t("price")}</small>
                    {levels.length ? (
                      levels.map(([price]) => (
                        <div className="queue-price" key={price}>
                          <strong>{price}</strong>
                          <div className="queue-orders">
                            {event.queue
                              .filter(
                                (o) =>
                                  o[1] === String(direction) && o[2] === price,
                              )
                              .map(([id, , , quantity]) => (
                                <div
                                  key={id}
                                  className="queue-order"
                                  data-own={id === "own"}
                                  data-order={id}
                                  style={{
                                    flexGrow: Math.max(1, Number(quantity)),
                                  }}
                                >
                                  <span>{t(id)}</span>
                                  <strong data-quantity={quantity}>
                                    {quantity}
                                  </strong>
                                </div>
                              ))}
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="queue-empty">{t("empty")}</p>
                    )}
                  </section>
                ))}
              </div>
              <div className="queue-fills" key={event.event_id}>
                <small>{t("fills")}</small>
                {event.fills.length ? (
                  event.fills.map((f, i) => (
                    <span
                      key={i}
                      data-fill-buy={f.buy_id}
                      data-fill-quantity={f.volume}
                    >
                      {t(f.buy_id)} · {f.volume} {t("quantity")} @ {f.price}
                    </span>
                  ))
                ) : (
                  <span>{t("none")}</span>
                )}
              </div>
            </div>
          );
        }}
      />
      <p className="event-note">{t("queue.scope")}</p>
      <details className="editorial-disclosure">
        <summary>{t("queue.table")}</summary>
        {Object.entries(evidence.cases).map(([id, item]) => (
          <section key={id} data-queue-table={id}>
            <h3>{t(id)}</h3>
            <div className="event-table">
              <table>
                <thead>
                  <tr>
                    <th>{t("queue.event")}</th>
                    <th>{t("arrival")}</th>
                    <th>{t("response")}</th>
                    <th>{t("fills")}</th>
                  </tr>
                </thead>
                <tbody>
                  {item.events.map((e) => (
                    <tr key={e.event_id}>
                      <td>{t(e.order_id)}</td>
                      <td>{e.effective_ns}</td>
                      <td>
                        {
                          item.reports.find((r) => r.event_id === e.event_id)!
                            .delivered_ns
                        }
                      </td>
                      <td>
                        {e.fills
                          .map((f) => `${f.buy_id} ${f.volume} @ ${f.price}`)
                          .join(" · ") || t("none")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="event-digest">
              {t("queue.provenance")} <code>{item.input_sha256}</code>
            </p>
          </section>
        ))}
      </details>
    </section>
  );
}
