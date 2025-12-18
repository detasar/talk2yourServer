"""
Shell Utilities

Common shell command execution functions used across the bot.
"""

import asyncio


async def run_command(cmd: str, timeout: int = 30) -> tuple[str, int]:
    """
    Run a shell command and return (output, return_code)

    Args:
        cmd: Shell command to execute
        timeout: Maximum seconds to wait

    Returns:
        Tuple of (stdout_output, return_code)
        On error, return_code is -1
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode('utf-8').strip(), proc.returncode
    except asyncio.TimeoutError:
        return "Command timed out", -1
    except Exception as e:
        return f"Error: {str(e)}", -1


async def run_command_separate_stderr(cmd: str, timeout: int = 30) -> tuple[str, str, int]:
    """
    Run command with separate stdout and stderr

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            stdout.decode('utf-8').strip(),
            stderr.decode('utf-8').strip(),
            proc.returncode
        )
    except asyncio.TimeoutError:
        return "", "Command timed out", -1
    except Exception as e:
        return "", f"Error: {str(e)}", -1
