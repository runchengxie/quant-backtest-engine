"""Localize one page's navigation, Material labels and language counterpart links."""

from copy import copy, deepcopy

from mkdocs.structure.nav import Navigation

_LABELS = {
    "en": ("Switch to dark mode", "Switch to light mode"),
    "zh": ("切换至深色模式", "切换至浅色模式"),
}


def on_page_context(context, page, config, nav):
    chinese = page.file.src_uri.endswith(".zh-CN.md")
    section = next(
        section
        for section in nav.items
        if section.title == ("简体中文" if chinese else "English")
    )
    pages = [
        item for item in nav.pages if item.file.src_uri.endswith(".zh-CN.md") == chinese
    ]
    context["nav"] = Navigation(section.children, pages)
    localized = copy(config)
    localized.theme = copy(config.theme)
    language = "zh" if chinese else "en"
    localized.theme.language = language
    palette = deepcopy(config.theme.get("palette"))
    for item in palette:
        item["toggle"]["name"] = _LABELS[language][
            0 if item["scheme"] == "default" else 1
        ]
    localized.theme.palette = palette
    english = page.file.src_uri.replace(".zh-CN.md", ".md")
    alternatives = []
    by_source = {item.file.src_uri: item.file for item in nav.pages}
    for label, locale, source in [
        ("English", "en", english),
        ("简体中文", "zh-CN", english[:-3] + ".zh-CN.md"),
    ]:
        target = by_source.get(source, by_source["index.md"])
        alternatives.append(
            {
                "name": label,
                "lang": locale,
                "link": config.site_url.rstrip("/") + "/" + target.url,
            }
        )
    localized.extra = {**config.extra, "alternate": alternatives}
    context["config"] = localized
    return context
