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
