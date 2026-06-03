# cmd_mcp
用于在 Windows 的 CMD 中执行任意命令并完整返回结果（包括标准输出、标准错误和退出码）的mcp

## 1.安装 fastmcp

`pip install fastmcp chardet`

## 2.保存脚本（例如 cmd.py）并在 Windows 11 或linux上运行

支持 MCP 的编辑器 可通过 stdio 连接本脚本。
客户端配置示例（VS Code settings.json 的 continue 部分）：

`

────────────────────────────────────────────────────────────────
1. VS Code Continue 插件（~/.continue/config.json 或 settings.json）
────────────────────────────────────────────────────────────────

{
  "experimental": {
    "mcpServers": {
      "cmd-executor": {
        "command": "D:\\env\\mcp\\python.exe",
        "args": ["C:\\Users\\AppData\\Roaming\\CherryStudio\\Data\\Agents\\8b3bqf6ew\\mcp_server.py"]
      }
    }
  }
}

如果需要让 AI agent 自动传入 conda_env，可另配一个别名版本：

{
  "experimental": {
    "mcpServers": {
      "cmd-executor-mcp": {
        "command": "D:\\env\\mcp\\python.exe",
        "args": ["C:\\Users\\AppData\\Roaming\\CherryStudio\\Data\\Agents\\8b3bqf6ew\\mcp_server.py"]
      }
    }
  }
}

────────────────────────────────────────────────────────────────

2. Claude Desktop（claude_desktop_config.json）
────────────────────────────────────────────────────────────────

{
  "mcpServers": {
    "cmd-executor": {
      "command": "D:\\env\\mcp\\python.exe",
      "args": ["C:\\Users\\AppData\\Roaming\\CherryStudio\\Data\\Agents\\8b3bqf6ew\\mcp_server.py"]
    }
  }
}

────────────────────────────────────────────────────────────────

3. Cursor / Windsurf / 其他支持 MCP 的编辑器
────────────────────────────────────────────────────────────────

配置方式类似，均设置为 stdio 模式：
  - command:  指定 python.exe 路径（如 D:\\env\\mcp\\python.exe）
  - args:     脚本绝对路径 + 无额外参数（transport=stdio 为默认）


Agent 调用 execute_command 工具时的 JSON 示例（含 conda_env）：

  # 使用系统默认 python（不推荐，可能被 Microsoft Store 别名拦截）
  { "command": "python -c \"print('hello')\"" }

  # 使用 conda base 环境的 python
  { "command": "python -c \"import torch; print(torch.__version__)\"", "conda_env": "base" }

  # 指定完整 python 可执行文件路径
  { "command": "python -c \"import sys; print(sys.version)\"", "conda_env": "D:\\env\\mcp\\python.exe" }

  # 指定环境根目录（自动补 python.exe）
  { "command": "pip list", "conda_env": "D:\\env\\mcp" }

  # 该环境下的任意命令（uvicorn, invoke, mcp 等）均会优先从 D:\\env\\mcp\\Scripts\\ 解析
  { "command": "uvicorn --version", "conda_env": "D:\\env\\mcp" }
  { "command": "invoke --version",   "conda_env": "D:\\env\\mcp" }
`
