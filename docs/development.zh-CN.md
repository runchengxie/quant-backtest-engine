# 开发与验证

Rust 最低版本为 1.99.0。Cargo.toml、Cargo.lock、LICENSE 和 COPYING 保留在根目录。
第三方说明放在 docs/third-party-notices.md，普通文档采用 kebab-case 文件名。

```sh
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo run --locked -- run fixtures/roundtrip.json
git diff --check
```

测试覆盖严格输入校验、无未来报价成交、费用、拒单、多标的持仓、重复运行和真实 CLI。
构建缓存、测试结果和保留的网页产物按工作区规范写入仓库之外。

## 文档站

Python 仅用于 MkDocs 工具，不参与 Rust 引擎运行。

```sh
uv venv --python 3.13 .venv-docs
uv pip sync --python .venv-docs/bin/python docs/requirements/docs.lock
.venv-docs/bin/mkdocs build --strict
.venv-docs/bin/python project_tools/check_docs.py --site-dir site
.venv-docs/bin/mkdocs serve
```

PR 只构建和检查，合并到 main 后通过 GitHub Actions 产物发布到 GitHub Pages。
不把生成网页提交进源码，不需要强制推送分支。

设计参考 quant-platform 的暖灰底色、棕色强调色和系统字体，以及
quant-backtest-runtime 的按语言过滤导航。英文为默认语言，中文页面有对应导航、
界面语言和深浅色按钮文字。主题选择由 Material 保留，切换语言跳到当前页面的对应译文。
缺少译文时回退英文首页。

## 主题维护

Material 官方[宣布于 2027 年 5 月 5 日结束维护](https://squidfunk.github.io/mkdocs-material/)。
当前锁定版本与同系列项目一致。应在此日期前评估上游后继方案或仍受维护的兼容主题。
正文保留为 Markdown，发布使用标准静态网页产物，便于后续迁移。

## 学习站点拼装

PR 与 main 执行相同检查，仅 main 发布。使用全新的仓库外 `TASK_DATA` 目录、Node 26.13.0/npm 12.2.2 以及锁定的 `web/package-lock.json`。前端依赖安装在外部目录，将其 `node_modules` 链接到 `web/`；Astro 生成状态也放在仓库外。文档环境安装带哈希的 `docs/requirements/docs.lock` 和 `learning.lock`。

```sh
python -m unittest project_tools.test_site_routes project_tools.test_reference_home project_tools.test_site_assembly project_tools.test_learning_assets -v
python project_tools/validate_learning_assets.py --manifest docs/assets/learning/manifest.json
npm --prefix web run check
npm --prefix web run test:unit
mkdocs build --strict --site-dir "$TASK_DATA/site-mkdocs"
python project_tools/check_docs.py --site-dir "$TASK_DATA/site-mkdocs"
python project_tools/extract_reference_home.py --site-dir "$TASK_DATA/site-mkdocs" --output "$TASK_DATA/reference-home"
SITE_INPUT_DIR="$TASK_DATA/reference-home" ASTRO_OUT_DIR="$TASK_DATA/site-astro" ASTRO_CACHE_DIR="$TASK_DATA/astro-cache" npm --prefix web run build
python project_tools/assemble_site.py --mkdocs "$TASK_DATA/site-mkdocs" --astro "$TASK_DATA/site-astro" --learning docs/assets/learning --routes docs/site/route-ownership.json --output "$TASK_DATA/site-assembled"
python project_tools/check_assembled_site.py --site-dir "$TASK_DATA/site-assembled" --base /quant-backtest-engine/ --legacy docs/site/legacy-route-anchors.json
SITE_DIR="$TASK_DATA/site-assembled" SITE_BASE=/quant-backtest-engine/ BROWSER_OUTPUT_DIR="$TASK_DATA/browser" npm --prefix web run test:e2e
```

浏览器检查前先安装锁定的 Playwright Chromium，或将 `CHROME_EXECUTABLE` 明确指向兼容的已安装 Chrome。测试启动器使用记录下来的空闲本地端口提供已构建产物。搜索范围仍是 MkDocs 技术参考；共享语言偏好不会重定向深链接。

唯一发布入口为 `.github/workflows/docs.yml`，只上传 `site-assembled`。`site-build.json` 绑定源码版本、源码/锁文件/manifest 输入及交付文件哈希。原教程保留 [PR 19](https://github.com/runchengxie/quant-backtest-engine/pull/19) 和提交 `4820af3b82940e7697cb8c92154315b1d59ee23d`，不提交历史渲染首页。
