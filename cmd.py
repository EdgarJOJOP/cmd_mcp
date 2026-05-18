from mcp.server.fastmcp import FastMCP
import asyncio
import chardet
import locale

# 创建 MCP 服务器实例
mcp = FastMCP("Windows CMD Executor")


def decode_best_effort(data: bytes) -> str:
    """多编码尝试，选取解码质量最好的结果。"""
    if not data:
        return ""

    # 1. 先用 chardet 检测
    detected = chardet.detect(data)
    chardet_enc = detected.get('encoding')
    chardet_conf = detected.get('confidence', 0)

    # 2. 构建候选编码列表（按优先级排列）
    candidates = []

    # 如果 chardet 置信度较高，优先使用
    if chardet_enc and chardet_conf > 0.7:
        candidates.append(chardet_enc)

    # UTF-8 始终加入候选（现代文件最常用）
    if not chardet_enc or chardet_enc.upper() != 'UTF-8':
        candidates.append('utf-8')

    # GBK（中文 Windows 默认 ANSI 编码）
    if not chardet_enc or 'GB' not in chardet_enc.upper():
        candidates.append('gbk')

    # chardet 结果即使置信度低也加上
    if chardet_enc and chardet_enc not in candidates:
        candidates.append(chardet_enc)

    # 系统默认编码
    sys_enc = locale.getpreferredencoding()
    if sys_enc.upper() not in [c.upper() for c in candidates]:
        candidates.append(sys_enc)

    # 其他常见编码作为兜底
    for enc in ['gb2312', 'utf-8-sig', 'utf-16', 'big5', 'shift_jis', 'euc-kr']:
        if enc.upper() not in [c.upper() for c in candidates]:
            candidates.append(enc)

    # 3. 逐个尝试，评估解码质量
    best_result = ""
    best_score = float('inf')

    for enc in candidates:
        try:
            result = data.decode(enc, errors='replace')
            # 评分：替换字符（ 和?）越少越好，控制字符（除\r\n\t外）越少越好
            replace_count = result.count('\ufffd') + result.count('?')
            ctrl_count = sum(1 for c in result if 0 < ord(c) < 32 and c not in '\r\n\t')
            score = replace_count * 10 + ctrl_count * 100

            if score < best_score:
                best_score = score
                best_result = result
        except (LookupError, UnicodeDecodeError):
            continue

    # 4. 如果都失败，强制 UTF-8 兜底
    if not best_result:
        best_result = data.decode('utf-8', errors='replace')

    return best_result


@mcp.tool()
async def execute_command(command: str) -> dict:
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
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=30
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "stdout": "",
                "stderr": "命令执行超时（30秒）",
                "returncode": -1,
                "error": "命令执行超时"
            }

        stdout_str = decode_best_effort(stdout)
        stderr_str = decode_best_effort(stderr)

        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": process.returncode,
            "error": None
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": f"命令执行失败: {str(e)}"
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
