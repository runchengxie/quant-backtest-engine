# 开发与网站构建

[English](development.md)

构建、环境、缓存和结果放在检出目录之外。Rust 要求1.99.0+，NautilusTrader 固定为0.66.0。网站现在由 Astro 统一生成：参考文档与互动教学共享页面框架、语言切换和同一个发布产物。

## 引擎检查

执行 `cargo fmt --all --check`、`cargo clippy --locked --all-targets -- -D warnings`、`cargo test --locked`、`cargo run --locked -- run fixtures/roundtrip.json`，以及 `python -m unittest project_tools.test_reusable_ownership -v`、`python project_tools/check_reusable_ownership.py` 和 `git diff --check`。将 `CARGO_TARGET_DIR` 指向外部任务目录。这些检查不代表冲击参数已校准或交易所行为已完整复刻。

## Astro 网站

使用 Node26.13.0、npm12.2.2 和已提交的前端锁。Python3.13 只准备可信文章内容及引擎产出的教学证据，不是第二个整站渲染器，也不在浏览器里核算金融结果。正式构建不安装或运行 MkDocs。保留固定版本的 Python-Markdown / PyMdown，是为了兼容已有 Markdown 方言和精确的旧标题锚点；所有 HTML 路由、页面布局及最终生成均由 Astro 负责。

在外部环境用 `uv pip sync --require-hashes` 安装 `docs/requirements/docs.lock` 和 `learning.lock`。前端依赖按不变的 `web/package-lock.json` 安装到任务独占目录，再把 `node_modules` 链接到 `web/`；Astro 生成文件和缓存也放在外部，不能与其他并行任务共用可写缓存。

完整命令见英文页；核心构建顺序如下，准备与输出目录必须是新的：

```sh
export PYTHON="$TASK_DATA/docs-env/bin/python"
export SITE_INPUT_DIR="$TASK_DATA/reference-input"
export ASTRO_OUT_DIR="$TASK_DATA/site-astro"
export ASTRO_CACHE_DIR="$TASK_DATA/astro-cache"
"$PYTHON" project_tools/prepare_reference.py --output "$SITE_INPUT_DIR"
npm --prefix web run build
"$PYTHON" project_tools/assemble_site.py --astro "$ASTRO_OUT_DIR" --learning docs/assets/learning --routes docs/site/route-ownership.json --output "$TASK_DATA/site-assembled"
"$PYTHON" project_tools/check_docs.py --site-dir "$TASK_DATA/site-assembled"
"$PYTHON" project_tools/check_assembled_site.py --site-dir "$TASK_DATA/site-assembled" --base /quant-backtest-engine/ --legacy docs/site/legacy-route-anchors.json
SITE_DIR="$TASK_DATA/site-assembled" SITE_BASE=/quant-backtest-engine/ BROWSER_OUTPUT_DIR="$TASK_DATA/browser" npm --prefix web run test:e2e
```

源码发生变化后要重新准备输入，再构建；旧内容凭据不能混用。验收还包括 `test_method_*`、`test_prepare_reference`、路由/首页/组装/学习资产测试、教学资产校验、`npm run check`、`npm run test:unit`、旧回放与 DOM 测试。DOM 工具使用单独锁定的 `project_tools/method-tests` 环境及 `NODE_PATH`。浏览器安装锁定 Playwright Chromium，或通过 `CHROME_EXECUTABLE` 使用兼容的本机浏览器。测试服务器只在已分配的本地端口运行并记录实际构建产物，无需长期预览服务。

## 阅读与交互

八个基础说明页都以一个大白话问题和一个联动主图开始。完整数值、来源及所有表格放在原生可展开区域，学习和实验旧地址都继续可用。参考文档搜索、旧 URL、锚点和下载保留；默认英文，中文对照和显式语言偏好沿用既有路由与存储约定。动画是可选项，尊重减少动态效果设置；禁用 JavaScript 时仍能展开完整记录表格。

浏览器只回放引擎产出的合成证据、把数值映射成图形，不重算账户，不把未知值改成零，不给确定情景编造概率。机会损失不是现金手续费，永久冲击系数是模型假设，有限可行格点也不代表已求出通用非凸问题或 HJB 的全局解。概念流程里的预测阶段，不表示示例给定订单来自训练好的策略。

视觉与讲解方式参考 [Distill 的互动优化文章](https://distill.pub/2017/momentum/)及 [Seeing Theory](https://github.com/seeingtheory/Seeing-Theory)，没有复制其代码或图形资产。[Astro 内容组织](https://docs.astro.build/en/guides/content-collections/)和 [Starlight 自定义页面](https://starlight.astro.build/guides/pages/)用于理解参考阅读与实验页面的分工，没有增加 Starlight 依赖。

## 发布与来源

唯一发布入口为 `.github/workflows/docs.yml`。PR 验证但不发布，合并后的 main 只上传组装好的 Astro 产物到 GitHub Pages。`site-build.json` 绑定实际源码、锁、输入清单及最终文件字节；陈旧片段会被拒绝。保留原教学 PR19 提交 `4820af3b82940e7697cb8c92154315b1d59ee23d` 的来源记录，不提交生成后的网站，也不因换渲染器重写金融样例的身份。

旧双渲染器和片段提取函数只作为历史测试工具保留，不构成隐含 MkDocs 构建依赖。许可原文与署名见[第三方说明](third-party-notices.zh-CN.md)、`LICENSE`、`COPYING`。
