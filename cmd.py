"""
MCP 服务器 —— 在 Shell (CMD/bash) 中执行命令，可选指定 conda 环境。

用法：
    agent 通过 MCP 协议调用 execute_command，可指定 conda_env 参数来
    让命令在指定 conda 环境中运行（自动使用该环境的 Python）。
    conda_env 可直接传 Python 可执行文件的路径。

示例 agent 调用（JSON）：
    { "command": "python -c \"print('hello')\"" }
    { "command": "python -c \"import torch; print(torch.__version__)\"", "conda_env": "base" }
    { "command": "python -c \"import sys; print(sys.version)\"", "conda_env": "D:\\env\\mcp\\python.exe" }
    { "command": "pip list", "conda_env": "D:\\env\\mcp" }
"""

from mcp.server.fastmcp import FastMCP
import asyncio
import chardet
import locale
import os
import sys
import platform
import shutil

# 创建 MCP 服务器实例
mcp = FastMCP("CMD Executor (conda-aware)")


# ==============================================================
# 1. conda / Python 探测工具
# ==============================================================

def _find_conda_base() -> str:
    """尝试找到 conda 的根目录。"""
    # 1) 环境变量
    for var in ("CONDA_EXE",):
        exe = os.environ.get(var)
        if exe:
            return os.path.dirname(os.path.dirname(exe))

    # 2) which/where
    conda_cmd = shutil.which("conda") or shutil.which("conda.bat") or ""
    if conda_cmd:
        return os.path.dirname(os.path.dirname(conda_cmd))

    # 3) Windows 常见安装路径
    if platform.system() == "Windows":
        for prefix in (
            os.path.expanduser("~\\miniconda3"),
            os.path.expanduser("~\\anaconda3"),
            "C:\\ProgramData\\miniconda3",
            "C:\\ProgramData\\anaconda3",
        ):
            if os.path.isdir(prefix):
                return prefix

    # 4) Linux 常见路径
    for prefix in (
        os.path.expanduser("~/miniconda3"),
        os.path.expanduser("~/anaconda3"),
        "/opt/miniconda3",
        "/opt/anaconda3",
    ):
        if os.path.isdir(prefix):
            return prefix

    return ""


def _resolve_python(python_spec: str) -> str:
    """
    将 conda_env 参数解析为 Python 可执行文件路径。

    支持三种形式：
      1) 直接路径（含 \ 或 /）→ 文件直接返回，目录自动补 python.exe
      2) 纯名称       → 当作 conda 环境名查找
      3) "base"       → conda 根目录的 Python
    """
    is_win = platform.system() == "Windows"
    py_name = "python.exe" if is_win else "bin/python"

    # --- 形式 1: 看起来是路径 ---
    if "\\" in python_spec or "/" in python_spec:
        if os.path.isfile(python_spec):
            return os.path.abspath(python_spec)
        # 可能是目录，补上 python.exe
        candidate = os.path.join(python_spec, py_name)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
        return ""

    # --- 形式 2 & 3: conda 环境名 ---
    conda_base = _find_conda_base()
    if not conda_base:
        return ""

    if python_spec == "base":
        candidate = os.path.join(conda_base, py_name)
        if os.path.isfile(candidate):
            return candidate

    candidate = os.path.join(conda_base, "envs", python_spec, py_name)
    if os.path.isfile(candidate):
        return candidate

    return ""


def _get_env_bin_dir(python_path: str) -> str:
    """根据 Python 可执行文件路径，返回该环境的 bin/Scripts 目录。"""
    py_dir = os.path.dirname(os.path.abspath(python_path))  # .../python.exe 所在目录
    parent = os.path.dirname(py_dir)                         # 环境根目录

    # 标准 conda 布局: <root>/python.exe, <root>/Scripts/pip.exe
    scripts = os.path.join(parent, "Scripts") if platform.system() == "Windows" else os.path.join(parent, "bin")
    if os.path.isdir(scripts):
        return scripts

    # 有些布局 python.exe 直接在根目录下且 Scripts 在同级
    scripts = os.path.join(py_dir, "Scripts") if platform.system() == "Windows" else os.path.join(py_dir, "bin")
    if os.path.isdir(scripts):
        return scripts

    return ""


def _patch_python_in_command(command: str, conda_python: str) -> str:
    """
    如果命令以 python/python3/py 开头，替换为指定环境的 Python（带 -u 禁用缓冲）。
    否则原样返回。
    """
    stripped = command.strip()

    # 识别 python / python3 / py 开头的命令 → 替换为指定 python
    for prefix in ("python ", "python3 ", "py "):
        if stripped.startswith(prefix):
            rest = stripped[len(prefix):].lstrip()
            return f'"{conda_python}" -u {rest}'

    if stripped in ("python", "python3", "py"):
        return f'"{conda_python}" -u'

    # pip → 转为 python -m pip，确保用对环境的 pip
    if stripped.startswith("pip "):
        rest = stripped[4:].lstrip()
        return f'"{conda_python}" -u -m pip {rest}'
    if stripped == "pip":
        return f'"{conda_python}" -u -m pip'

    return command


# ==============================================================
# 2. 解码工具
# ==============================================================

def decode_best_effort(data: bytes) -> str:
    """多编码尝试，选取解码质量最好的结果。"""
    if not data:
        return ""

    detected = chardet.detect(data)
    chardet_enc = detected.get('encoding')
    chardet_conf = detected.get('confidence', 0)

    candidates = []

    if chardet_enc and chardet_conf > 0.7:
        candidates.append(chardet_enc)
    if not chardet_enc or chardet_enc.upper() != 'UTF-8':
        candidates.append('utf-8')
    if not chardet_enc or 'GB' not in chardet_enc.upper():
        candidates.append('gbk')
    if chardet_enc and chardet_enc not in candidates:
        candidates.append(chardet_enc)
    sys_enc = locale.getpreferredencoding()
    if sys_enc.upper() not in [c.upper() for c in candidates]:
        candidates.append(sys_enc)
    for enc in ['gb2312', 'utf-8-sig', 'utf-16', 'big5', 'shift_jis', 'euc-kr']:
        if enc.upper() not in [c.upper() for c in candidates]:
            candidates.append(enc)

    best_result = ""
    best_score = float('inf')

    for enc in candidates:
        try:
            result = data.decode(enc, errors='replace')
            replace_count = result.count('\ufffd') + result.count('?')
            ctrl_count = sum(1 for c in result if 0 < ord(c) < 32 and c not in '\r\n\t')
            score = replace_count * 10 + ctrl_count * 100
            if score < best_score:
                best_score = score
                best_result = result
        except (LookupError, UnicodeDecodeError):
            continue

    if not best_result:
        best_result = data.decode('utf-8', errors='replace')

    return best_result


# ==============================================================
# 3. MCP Tool：execute_command
# ==============================================================

@mcp.tool()
async def execute_command(command: str, conda_env: str = "") -> dict:
    """
    在系统的 Shell (CMD/bash) 中执行命令。

    — 指定 conda_env 后自动使用指定的 Python 解释器

    Args:
        command: 要执行的命令字符串
        conda_env: （可选）Python 可执行文件的路径，或 conda 环境名。
                   例如 "base"、"D:\\env\\mcp\\python.exe"、"D:\\env\\mcp"。
                   指定后，以 python/python3/py 开头的命令会
                   自动替换为该 Python 解释器。

    Returns:
        dict: { stdout, stderr, returncode, error }
    """
    try:
        final_command = command
        hint = ""

        # 如果指定了 conda 环境 / Python 路径，解析并替换命令
        if conda_env:
            conda_python = _resolve_python(conda_env)
            if conda_python:
                # 1) 替换 python/python3/py 前缀为指定 python
                final_command = _patch_python_in_command(command, conda_python)
                # 2) 把环境的 Scripts/bin 目录加到 PATH 最前面
                _add_env_to_path = _get_env_bin_dir(conda_python)
            else:
                _add_env_to_path = ""
                hint = f"[提示] 未找到 conda 环境或 Python 路径 '{conda_env}'，使用系统默认 Python 执行\n"
        else:
            _add_env_to_path = ""

        # 构建环境变量
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        if _add_env_to_path:
            env["PATH"] = _add_env_to_path + os.pathsep + env["PATH"]

        # 🐛 关键修复：子进程不继承 MCP 的 stdin
        process = await asyncio.create_subprocess_shell(
            final_command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=60
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "stdout": "",
                "stderr": "命令执行超时（60秒）",
                "returncode": -1,
                "error": "命令执行超时",
            }

        stdout_str = decode_best_effort(stdout)
        stderr_str = decode_best_effort(stderr)

        # 如果有 conda 提示信息，追加到 stderr 前面
        if hint:
            stderr_str = hint + stderr_str

        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": process.returncode,
            "error": None,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": f"命令执行失败: {str(e)}",
        }


# ==============================================================
# 4. 入口
# ==============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
