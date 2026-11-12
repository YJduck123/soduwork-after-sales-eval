# SoduWork 售后插件复用实测

选题：把店铺售后处理方法做成 SoduWork 插件，换账号、换工单检验复用。

当前状态：实验已完成。账号 A 创建插件 v1.0.0 并上架，账号 B 完成 B1（完整方法）和 B2（插件）对照测试，两组核心字段均 12/12 匹配。详细结果见 `experiment-report.md`。

## 当前文件

- [实验安排](experiment.md)：分组、步骤、证据要求与文章主线。
- [模拟店铺政策](inputs/policy.md)：各组共用的业务规则和输出约定。
- [开发工单](inputs/development.json)：12 条，用于首轮处理、纠错和制作插件。
- [留出工单](inputs/transfer.json)：12 条，只在插件冻结后使用。
- [操作提示词](prompts.md)：首次处理、制作插件、跨账号复测。
- [评分脚本](evaluation/score.mjs)：按单核对处理建议、金额、运费与关键政策覆盖。
- [环境核验记录](evidence/environment/2026-11-12-setup.md)：版本、启动结果、界面观察与下一步。
- `evaluation/expected.json`：评测者持有的标准答案，不提供给被测 Agent。

校验材料和评分器：

```powershell
node .\evaluation\score.mjs --self-test
```

评分一次真实输出：

```powershell
node .\evaluation\score.mjs transfer "完整路径\results.json"
```

评分器自检与工单设计均由当前 Codex 完成，不能写成 SoduWork 的交付或测试成绩。人工仍需检查政策解释、事实引用和客户回复。

## 来源

- [评测范围 PDF](C:/Users/86155/Desktop/SoduWork开源项目KOL评测范围建议指南.pdf)。
- 合作 Brief：https://my.feishu.cn/wiki/Xa3Vw7MexiSiSykhW5Jcd8tVn4d
- 源码：https://github.com/mdiri-ai/SoduWork
- 启动文档：https://github.com/mdiri-ai/SoduWork/blob/main/docs/getting-started.md
- 旧项目 `../电商售后争议裁决助手/app/data/cases.json` 仅启发了功能故障、错发和物流争议等场景。本次工单重新编写，未沿用旧项目的模型结果或图片。

2026-11-12 环境检查：常见安装目录、卸载记录、进程和默认服务端口中未发现 SoduWork；Node.js 为 v22.21.0，本机已有 uv 管理的 Python 3.12.12。未安装新解释器、修改 PATH 或探测模型供应商。

随后用官方源码启动了独立实例：客户端版本 `1.13.15`，提交 `0ead3d42c61cf387d26546ef6635d205331153d6`。本地管理地址为 `http://127.0.0.1:18989`，源码与私有数据都位于 `.runtime/`，不应随文章素材或开源包一起分发。
