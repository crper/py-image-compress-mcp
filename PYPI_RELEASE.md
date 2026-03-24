# PyPI 发布指南

本指南详细说明如何将 py-image-compress-mcp 发布到 PyPI。

## 前置条件

1. **PyPI 账户**：在 [PyPI](https://pypi.org) 和 [TestPyPI](https://test.pypi.org) 创建账户
2. **API 令牌**：为 PyPI 和 TestPyPI 生成 API 令牌
3. **uv 工具**：确保已安装 uv 用于构建和发布

## 设置 API 令牌

### 创建 API 令牌
1. 访问 PyPI 账户设置 → API 令牌
2. 创建新令牌，范围选择"整个账户"或特定项目
3. 安全保存令牌（只显示一次）

### 配置 uv 令牌
```bash
# TestPyPI（测试环境）
export UV_PUBLISH_TOKEN="pypi-your-test-token-here"

# PyPI（生产环境）
export UV_PUBLISH_TOKEN="pypi-your-production-token-here"
```

## 发布流程

### 1. 发布前检查

```bash
# 确保校验和示例都通过
uv run ruff check src tests examples scripts
uv run ruff format --check src tests examples scripts
uv run mypy src tests
uv run pytest -q
make examples

# 检查版本一致性
grep '^version' pyproject.toml
uv run python -c "from py_image_compress_mcp import __version__; print(__version__)"

# 如需要，更新 pyproject.toml 中的版本号
# 如果你维护发布说明，再同步更新 GitHub Release 文案
```

### 2. 构建包

```bash
# 清理之前的构建
rm -rf dist/

# 构建源码分发包和轮子包
uv build

# 验证构建内容
tar -tzf dist/py_image_compress_mcp-*.tar.gz | head -20
```

### 3. TestPyPI 测试（推荐）

```bash
# 首先发布到 TestPyPI 测试
UV_PUBLISH_TOKEN="pypi-your-test-token" uv publish --publish-url https://test.pypi.org/legacy/

# 从 TestPyPI 安装测试
pip install --index-url https://test.pypi.org/simple/ py-image-compress-mcp

# 测试安装的包
py-image-compress-mcp --version
```

### 4. 发布到 PyPI

```bash
# 发布到正式 PyPI
UV_PUBLISH_TOKEN="pypi-your-production-token" uv publish

# 在 PyPI 上验证
# 访问：https://pypi.org/project/py-image-compress-mcp/
```

### 5. 发布后操作

```bash
# 创建 git 标签（以实际版本号为准）
git tag vX.Y.Z
git push origin vX.Y.Z

# 从 PyPI 测试安装
pip install py-image-compress-mcp

# 测试命令入口
py-image-compress-mcp --version
uvx py-image-compress-mcp --version
```

## 版本管理

### 语义化版本控制
- **主版本** (X.0.0)：不兼容的 API 修改
- **次版本** (0.X.0)：向下兼容的功能性新增
- **修订版本** (0.0.X)：向下兼容的问题修正

### 更新版本
使用 uv 内置的版本管理功能：

```bash
# 更新到指定版本
uv version 1.0.0

# 语义化版本递增
uv version --bump major    # 主版本 +1
uv version --bump minor    # 次版本 +1
uv version --bump patch    # 修订版本 +1

# 预览版本变更（不实际修改）
uv version 2.0.0 --dry-run

# 手动更新（如果需要）
# 1. 更新 pyproject.toml 中的 version
# 2. 提交变更后再构建
```

## 故障排除

### 常见问题

**构建失败**：检查 pyproject.toml 语法和依赖
```bash
uv build --verbose
```

**上传失败**：验证 API 令牌和网络连接
```bash
UV_PUBLISH_TOKEN="your-token" uv publish --verbose
```

**版本冲突**：确保版本在 PyPI 上不存在
```bash
# 检查现有版本
pip index versions py-image-compress-mcp
```

**权限问题**：确保令牌有正确的权限范围

### 包验证

```bash
# 检查包元数据
uv run python -c "import py_image_compress_mcp; print(py_image_compress_mcp.__version__)"

# 验证入口点
uv run py-image-compress-mcp --version
```

## 安全注意事项

- 永远不要将 API 令牌提交到版本控制
- 使用环境变量或安全凭据存储
- 考虑使用 GitHub Actions 进行自动化发布
- 定期轮换 API 令牌

## 自动化发布（当前仓库）

当前仓库已经通过 [`.github/workflows/ci.yml`](.github/workflows/ci.yml) 在 GitHub Release 事件上执行构建和 `uv publish`。

如果要继续使用这条自动化链路，请确认：

- 仓库密钥里已配置 `PYPI_API_TOKEN`
- Release 是从经过验证的提交创建的
- 发布前已手动跑过“发布前检查”一节里的命令

## 高级配置

### 使用自定义索引

如果使用自定义包索引，在 `pyproject.toml` 中配置：

```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true
```

然后使用：
```bash
uv publish --index testpypi
```

### 可信发布者（推荐）

对于 GitHub Actions，推荐使用 PyPI 的可信发布者功能，无需手动管理令牌：

1. 在 PyPI 项目设置中添加可信发布者
2. 配置 GitHub Actions 工作流
3. 无需设置 `UV_PUBLISH_TOKEN`

详见：[PyPI 可信发布者文档](https://docs.pypi.org/trusted-publishers/)
