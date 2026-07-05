# Contributing

感谢你参与维护 Risk-HiMATE。

这个仓库当前处于“研究原型 -> 可展示工程”过渡阶段，所以协作时最重要的不是大规模重构，而是让每次改动都更稳定、更可解释、更适合演示和后续扩展。

## 开发原则

1. 优先保持 pipeline 可运行
2. 优先减少误报和不稳定输出
3. 所有新能力尽量补测试
4. Prompt、schema、pipeline 三者要一起考虑
5. 不要把生成物、临时报告和虚拟环境提交进仓库

## 推荐提交流程

1. 新建分支
2. 完成小范围改动
3. 运行测试
4. 自查 README / prompt / schema 是否需要同步更新
5. 发起 Pull Request

## 本地检查

运行全量测试：

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

常见重点检查项：

- `risk_himate/app/llm/prompts/` 的 prompt 结构是否仍然稳定
- `risk_himate/app/workflows/pipeline.py` 是否仍然能输出 `report` 和 `debug`
- `risk_himate/app/core/schemas.py` 是否与输出 JSON 保持一致
- `risk_himate/app/agents/reflection_agent.py` 是否引入新的误修正

## 提交建议

比较适合的提交粒度：

- 一个功能
- 一个 bugfix
- 一类 prompt 优化
- 一次 README / docs 完整更新

不建议把这些混在同一个提交里：

- prompt 大改
- scoring 逻辑变更
- collector 接口变更
- 前端展示改动

## 重点风险

当前仓库最容易出问题的几个点：

- 地缘博弈风险误报
- PDF 文本抽取后的噪声 chunk
- LLM 与规则 fallback 混合路径
- severity 被 reflection 错误降级

如果你改到了这些地方，请补回归测试。
