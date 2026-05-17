from mcp.server.fastmcp import FastMCP
import subprocess
import sys

# 创建 MCP 服务器实例，名称为 "Windows CMD Executor"
mcp = FastMCP("Windows CMD Executor")

@mcp.tool()
def execute_command(command: str) -> dict:
    """
    在 Windows 11 的 CMD 中执行命令，并返回完整的结果。

    Args:
        command: 要执行的命令字符串，例如 "dir" 或 "ping 127.0.0.1"

    Returns:
        dict: 包含以下字段：
            - stdout: 标准输出内容
            - stderr: 标准错误内容
            - returncode: 退出码（0 表示成功）
            - error: 若执行出错则为错误描述，否则为 None
    """
    try:
        # 使用 subprocess.run 执行命令，shell=True 支持 CMD 内部命令
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,          # 超时时间，防止命令阻塞
            encoding='gbk'       # Windows 中文系统常用编码（若输出乱码可改为 'utf-8'）
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": None
        }
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "error": f"命令执行超时: {str(e)}"
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": f"命令执行失败: {str(e)}"
        }

if __name__ == "__main__":
    # 以 stdio 传输模式启动 MCP 服务器（适合与支持 MCP 的客户端集成）
    mcp.run(transport="stdio")
