# cmd_mcp
用于在 Windows 的 CMD 中执行任意命令并完整返回结果（包括标准输出、标准错误和退出码）的mcp

## 1.安装 fastmcp

`pip install fastmcp`

## 2.保存脚本（例如 cmd_executor.py）并在 Windows 11 上运行

支持 MCP 的编辑器 可通过 stdio 连接本脚本。
客户端配置示例（VS Code settings.json 的 continue 部分）：

`
Json
"mcpServers": {
  "cmd-executor": {
    "command": "python",
    "args": ["path/to/cmd_executor.py"]
  }
}`
