.PHONY: help setup dev test typecheck benchmark run examples clean

help:
	@echo "常用命令:"
	@echo "  setup    - 安装依赖和配置开发环境"
	@echo "  dev      - 开发模式：格式化+检查+测试"
	@echo "  test     - 运行测试"
	@echo "  typecheck- 运行类型检查"
	@echo "  benchmark- 运行性能基准"
	@echo "  run      - 启动 MCP 服务器"
	@echo "  examples - 运行示例演示"
	@echo "  clean    - 清理文件"

setup:
	uv sync
	uv run pre-commit install

dev:
	uv run ruff format src/ tests/ examples/
	uv run ruff check src/ tests/ examples/ --fix
	uv run mypy src tests
	uv run pytest tests/ -v

test:
	uv run pytest tests/ -v

typecheck:
	uv run mypy src tests

benchmark:
	uv run python scripts/benchmark.py

run:
	uv run python -m py_image_compress_mcp

examples:
	@echo "运行示例演示..."
	uv run python examples/mcp_usage.py

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage
	find . -name __pycache__ -exec rm -rf {} \; 2>/dev/null || true
