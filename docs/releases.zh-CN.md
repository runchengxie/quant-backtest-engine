# 实验性发行包

[English](releases.md)

首个下载版本属于实验性版本，仅提供 Linux x86_64、glibc 环境下的 CLI，
使用 Ubuntu 22.04（glibc 2.35）、Rust 1.99.0 和锁定的 NautilusTrader 0.66.0
依赖构建。暂不提供其他操作系统或 musl 版本，也不发布到 crates.io。
首个预发行版发布前，请按[快速开始](quickstart.zh-CN.md)从源码运行。

在 [GitHub Releases](https://github.com/runchengxie/quant-backtest-engine/releases)
下载同一预发行版的以下三个文件。

- `quant-backtest-engine-0.2.0-x86_64-unknown-linux-gnu.tar.gz`，可执行文件、
  LGPL/GPL 许可原文、依赖声明和构建元数据。
- `quant-backtest-engine-0.2.0-x86_64-unknown-linux-gnu-source.tar.gz`，对应的
  应用源码、`Cargo.lock`、全部 Rust 依赖源码及其发布包所带的许可原文、
  Cargo 离线配置和 `REBUILD.md`。
- `SHA256SUMS`，两个压缩包的校验值。解压前运行
  `sha256sum --check SHA256SUMS`。校验值用于检测文件是否损坏。核实发布者身份需要另外验证数字签名。

解压二进制包后，在其目录内运行 `./quant-backtest-engine capabilities`。
使用 `./quant-backtest-engine run REQUEST.json` 执行请求。源码包内的
`fixtures/roundtrip.json` 可用于合成数据试跑。构建元数据记录 Git 提交、
锁文件哈希、编译器、Cargo、平台和 glibc 版本。程序仍依赖系统 C 运行库。

程序静态链接 Rust 依赖，其中包括采用 LGPL 的 NautilusTrader crate。
对应的完整源码允许接收者修改依赖、重新构建和链接应用。源码包的
`REBUILD.md` 提供离线命令，并说明修改 vendor 源码时如何处理校验文件。
需先安装 Rust 1.99.0 和本机编译工具，这些工具不在包内。打包流程支持按
相同源码重建，不保证不同机器产物逐字节相同，也不构成法律合规保证。
再分发时应保留适用的版权及许可声明，参见[第三方声明](third-party-notices.zh-CN.md)。

## 维护者打包流程

先提交更改，确认 Linux x86_64 源码目录没有未提交内容，再用 Python 3.11 或更新版本运行下面的命令。

```bash
python3 project_tools/package_release.py --output /absolute/external/release-output
```

需要保留的产物应放在项目约定的数据目录。脚本从已提交的 Git 树取源码，
按锁文件收集依赖，并在依赖缺少许可或声明文件时停止。少数 crate 发布包
未带仓库级许可文件，脚本仅对明确列出的版本从对应上游提交补齐，并附上
objc2 上游明确提供的 Apache 许可原文。下载内容按 SHA-256 固定，来源 URL、
提交和哈希记录在 `dependency-licenses.json` 中。原文保留在两个压缩包内，
不修改 vendor 中的 crate 文件。随后使用空 Cargo
目录离线运行 release 配置的 `cargo test` 和构建，再从解压后的二进制包执行
能力查询，并核对合成案例的权益（10019.78）和手续费（0.22）。初始依赖收集和工具链安装需要
联网。临时构建目录在打包后删除。

`Experimental Linux release` 工作流在 PR 上构建，上传的产物保留七天。
手动运行默认 `publish=false`，也只上传产物。合并并检查后，在 `main` 上以
`publish=true` 和新标签（如 `v0.2.0-alpha.1`）运行，才会发布 GitHub 预发行版。
构建任务仅有 `contents: read`，发布任务才有 `contents: write`。标签指向本次
验证的提交。流程不发布 crates.io。不要重复使用已有的标签或发行版名称。
如果发布请求丢失响应，应先查询远端发行版和标签状态，再决定是否重试。
