# 给 AI 编程助手的说明

- 改完代码必须通过：`uv run ruff check src tests`、`uv run mypy`、`uv run pytest -q`
- 代码注释和面向用户的文字用简体中文；给模型看的提示词、工具描述用英文
- 模型要执行的命令只能经过 `sandbox/` 里的 runner，不要在别处直接调用 subprocess
- 新增工具：在 `tools/` 里继承 `Tool`，声明 `risk`；会碰文件的工具必须用 `resolve_in_workspace`
- 改了沙盒规则或权限策略，要在 `tests/test_sandbox.py` / `tests/test_policy.py` 里加对应的测试
- 新增评测题：`evals/tasks/<编号>-<名字>/`，包含 `task.toml` 和 `repo/`（repo 根目录放一个 `conftest.py`）
