"""Expand local fixtures to complete no-JS tables plus optional replay payloads."""

import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets/method"


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri not in {
        "backtesting-explained.md",
        "backtesting-explained.zh-CN.md",
    }:
        return markdown
    language = "zh-CN" if page.file.src_uri.endswith(".zh-CN.md") else "en"
    english = json.loads((ASSETS / "en.json").read_text())
    locale = json.loads((ASSETS / (language + ".json")).read_text())
    data = json.loads((ASSETS / "fixtures.json").read_text())

    def t(key):
        return html.escape(locale.get(key, english.get(key, key)))

    def display(key, value):
        if value is None:
            return t("value.unknown")
        if isinstance(value, bool):
            return t("value." + str(value).lower())
        return t("phase." + value) if key == "phase" else html.escape(str(value))

    def replace(match):
        ident = match.group(1)
        scene = data["scenes"][ident]
        options = "".join(
            f'<option value="{i}">{t("scenario." + s["id"])}</option>'
            for i, s in enumerate(scene["scenarios"])
        )
        tables = []
        for case_index, scenario in enumerate(scene["scenarios"]):
            columns = list(
                dict.fromkeys(key for row in scenario["states"] for key in row)
            )
            header = "".join(
                f'<th scope="col">{t("field." + key)}</th>' for key in columns
            )
            rows = "".join(
                f'<tr data-scenario="{scenario["id"]}" data-frame="{i}">'
                + "".join(f"<td>{display(key, row.get(key))}</td>" for key in columns)
                + "</tr>"
                for i, row in enumerate(scenario["states"])
            )
            tables.append(
                f'<details class="method-case" data-method-case="{scenario["id"]}" {"open" if case_index == 0 else ""}><summary>{t("scenario." + scenario["id"])}</summary><p>{t("units." + (scenario["id"] if ident == "risk" else ident))}</p><div class="method-scroll" tabindex="0" role="region" aria-label="{t("scenario." + scenario["id"])}"><table><caption>{t("table")}</caption><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div></details>'
            )
            if "grid" in scenario:
                gridrows = "".join(
                    "<tr>"
                    + "".join(
                        f"<td>{display(key, row[key])}</td>"
                        for key in ["shares", "feasible", "cash"]
                    )
                    + "</tr>"
                    for row in scenario["grid"]
                )
                tables.append(
                    "<details><summary>"
                    + t("diagram.grid")
                    + '</summary><div class="method-scroll"><table><thead><tr>'
                    + "".join(
                        '<th scope="col">' + t("field." + key) + "</th>"
                        for key in ["shares", "feasible", "cash"]
                    )
                    + "</tr></thead><tbody>"
                    + gridrows
                    + "</tbody></table></div></details>"
                )
        provenance = []
        for s in scene["scenarios"]:
            owner = data["owners"][s["owner"]]
            links = []
            for source in s["source"]:
                base = (
                    owner["url"]
                    if source.startswith("packages/") or s["owner"] == "engine"
                    else "https://github.com/runchengxie/quant-backtest-engine/tree/main"
                )
                links.append(f'<a href="{base}/{source}">{html.escape(source)}</a>')
            provenance.append(
                f"<p>{t('scenario.' + s['id'])} · <code>{owner['revision']}</code><br>"
                + ", ".join(links)
                + f"<br>input SHA-256 <code>{s['input_sha256']}</code></p>"
            )
        # Keep complete provenance in the downloadable authoritative fixture.
        # Replay only needs these fields; raw numeric ns clocks are unsafe in JS.
        replay_scene = {
            "scenarios": [
                {key: s[key] for key in ("id", "states", "grid") if key in s}
                for s in scene["scenarios"]
            ]
        }
        payload = json.dumps(
            {"id": ident, "scene": replay_scene, "english": english, "locale": locale},
            ensure_ascii=False,
            allow_nan=False,
        ).replace("<", "\\u003c")
        return f'''<section class="method-scene" aria-label="{t("visual." + ident)}">
<p class="method-boundary">{t("boundary." + ident)}</p>
<div class="method-controls" hidden><label for="method-{ident}-scenario">{t("scenario")}</label><select id="method-{ident}-scenario">{options}</select><button type="button" data-action="play" aria-pressed="false">{t("play")}</button><button type="button" data-action="step">{t("step")}</button><button type="button" data-action="reset">{t("reset")}</button></div>
<div class="method-stage" hidden><svg viewBox="0 0 500 295" aria-hidden="true" focusable="false"></svg><p class="method-status" role="status" aria-live="polite" aria-atomic="true"></p><p>{t("motion")}</p></div>
{"".join(tables)}
<details><summary>{t("sources")}</summary>{"".join(provenance)}<p>exporter SHA-256 <code>{data["exporter_sha256"]}</code></p></details>
<script type="application/json" class="method-payload">{payload}</script>
</section>'''

    return re.sub(r"<!-- method:([a-z]+) -->", replace, markdown)
