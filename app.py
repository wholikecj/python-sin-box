#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGSBX Sing-box 部署脚本

提供 Sing-box 内核的安装、更新、卸载、服务管理等功能，
支持 Hysteria2、Tuic、AnyTLS、Any-Reality、Shadowsocks-2022、Vmess-ws、Socks5 等协议。
"""

import os
import sys
import json
import socket
import subprocess
import platform
import re
import random
import base64
import shutil
import threading
from typing import Dict, Any
import uuid as uuid_lib
from http.server import HTTPServer, BaseHTTPRequestHandler

# 全局变量定义
AGSBX_HOME = os.path.join(os.path.expanduser("~"), "app")
AGSBX_DATA = os.path.join(os.path.expanduser("~"), "app-data")

# 确保必要的目录存在
os.makedirs(AGSBX_HOME, exist_ok=True)
os.makedirs(os.path.join(AGSBX_DATA, "common"), exist_ok=True)
os.makedirs(os.path.join(AGSBX_DATA, "singbox"), exist_ok=True)


def get_arch() -> str:
    """
    获取系统架构标识符

    Returns:
        str: 架构标识符 (arm64/amd64)
    """
    machine = platform.machine().lower()
    print(f"检测到系统架构: {machine}")

    if machine in ("arm64", "aarch64", "armv8l"):
        return "arm64"
    elif machine in ("amd64", "x86_64", "i686", "i386"):
        return "amd64"
    else:
        arch_map = {
            "armv7l": "arm64",
            "ppc64le": "amd64",
            "s390x": "amd64",
        }
        result = arch_map.get(machine, "amd64")
        print(f"未知架构 {machine}，默认使用: {result}")
        return result


def run_command(cmd: list, timeout: int = 30) -> tuple:
    """
    执行系统命令并返回输出

    Args:
        cmd: 命令列表或字符串
        timeout: 超时时间(秒)

    Returns:
        tuple: (returncode, stdout, stderr)
    """
    try:
        if isinstance(cmd, str):
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, shell=True
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)


def has_command(cmd: str) -> bool:
    """
    检查命令是否存在

    Args:
        cmd: 命令名称

    Returns:
        bool: 命令是否存在
    """
    return shutil.which(cmd) is not None


def v4v6_main() -> Dict[str, str]:
    """
    获取服务器 IPv4/IPv6 地址及运营商信息

    Returns:
        dict: 包含 v4, v6, v4dq, v6dq 的字典
    """
    v46url = "https://icanhazip.com"
    v4 = ""
    v6 = ""
    v4dq = ""
    v6dq = ""

    # 获取 IPv4 地址
    if has_command("curl"):
        rc, v4, _ = run_command(["curl", "-s4m5", "-k", v46url])
    elif has_command("wget"):
        rc, v4, _ = run_command(["wget", "-4", "--tries=2", "-qO-", v46url])
    else:
        rc, v4 = -1, ""
    v4 = str(v4).strip() if v4 else ""

    # 获取 IPv6 地址
    if has_command("curl"):
        rc, v6, _ = run_command(["curl", "-s6m5", "-k", v46url])
    elif has_command("wget"):
        rc, v6, _ = run_command(["wget", "-6", "--tries=2", "-qO-", v46url])
    else:
        _, v6 = -1, ""
    v6 = str(v6).strip() if v6 else ""

    # 获取 IPv4 运营商信息
    if has_command("curl"):
        output, _, _ = run_command(["curl", "-s4m5", "-k", "https://ip.fm"])
        output = str(output) if output else ""
        if output:
            match = re.search(r"Location:\s*([^,]+)", output)
            if match:
                v4dq = match.group(1).strip()
    elif has_command("wget"):
        output, _, _ = run_command(["wget", "-4", "--tries=2", "-qO-", "https://ip.fm"])
        output = str(output) if output else ""
        if output:
            match = re.search(r"Location:\s*([^<]+)<", output)
            if match:
                v4dq = match.group(1).strip()

    # 获取 IPv6 运营商信息
    if has_command("curl"):
        output, _, _ = run_command(["curl", "-s6m5", "-k", "https://ip.fm"])
        output = str(output) if output else ""
        if output:
            match = re.search(r"Location:\s*([^<]+)<", output)
            if match:
                v6dq = match.group(1).strip()
    elif has_command("wget"):
        output, _, _ = run_command(["wget", "-6", "--tries=2", "-qO-", "https://ip.fm"])
        output = str(output) if output else ""
        if output:
            match = re.search(r"Location:\s*([^<]+)<", output)
            if match:
                v6dq = match.group(1).strip()

    v4 = v4.strip()
    v6 = v6.strip()

    # 保存到文件
    with open(os.path.join(AGSBX_DATA, "common", "v4"), "w") as f:
        f.write(v4)
    with open(os.path.join(AGSBX_DATA, "common", "v6"), "w") as f:
        f.write(v6)
    with open(os.path.join(AGSBX_DATA, "common", "v4dq"), "w") as f:
        f.write(v4dq)
    with open(os.path.join(AGSBX_DATA, "common", "v6dq"), "w") as f:
        f.write(v6dq)

    return {"v4": v4, "v6": v6, "v4dq": v4dq, "v6dq": v6dq}


def read_file(path: str) -> str:
    """读取文件内容，如果文件不存在返回空字符串"""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def write_file(path: str, content: str) -> None:
    """写入文件内容"""
    with open(path, "w") as f:
        f.write(content)


def check_warp() -> Dict[str, str]:
    """
    检查并配置 WARP

    Returns:
        dict: 包含 warp_private_key, warp_ipv6, warp_reserved 的字典
    """
    warpurl = "https://warp.xijp.eu.org"
    wpv6 = ""
    pvk = ""
    res = ""

    # 默认 WARP 配置（备用）
    default_wpv6 = "2606:4700:110:8d8d:1845:c39f:2dd5:a03a"
    default_pvk = "52cuYFgCJXp0LAq7+nWJIbCXXgU9eGggOc+Hlfz5u6A="
    default_res = "[215, 69, 233]"

    if has_command("curl"):
        _, output, _ = run_command(["curl", "-sm5", "-k", warpurl])
    elif has_command("wget"):
        _, output, _ = run_command(["wget", "--tries=2", "-qO-", warpurl])
    else:
        # 没有下载工具，使用默认值
        wpv6 = default_wpv6
        pvk = default_pvk
        res = default_res
        write_file(os.path.join(AGSBX_DATA, "common", "warp_private_key"), pvk)
        write_file(os.path.join(AGSBX_DATA, "common", "warp_ipv6"), wpv6)
        write_file(os.path.join(AGSBX_DATA, "common", "warp_reserved"), res)
        return {"wpv6": wpv6, "pvk": pvk, "res": res}

    output = str(output) if output else ""
    if not output or "html" in output.lower():
        # 获取失败或返回 HTML，使用默认值
        wpv6 = default_wpv6
        pvk = default_pvk
        res = default_res
    else:
        # 解析 Private_key
        match = re.search(r"Private_key[：:]\s*(\S+)", output)
        if match:
            pvk = match.group(1).strip()
        else:
            pvk = default_pvk

        # 解析 IPV6
        match = re.search(r"IPV6[：:]\s*(\S+)", output)
        if match:
            wpv6 = match.group(1).strip()
        else:
            wpv6 = default_wpv6

        # 解析 reserved
        match = re.search(r"reserved[：:]\s*(\[.*?\])", output)
        if match:
            res = match.group(1).strip()
        else:
            res = default_res

    # 保存到文件
    write_file(os.path.join(AGSBX_DATA, "common", "warp_private_key"), pvk)
    write_file(os.path.join(AGSBX_DATA, "common", "warp_ipv6"), wpv6)
    write_file(os.path.join(AGSBX_DATA, "common", "warp_reserved"), res)

    return {"wpv6": wpv6, "pvk": pvk, "res": res}


def config_warp_outbound(warp_mode: str = "sx") -> Dict[str, Any]:
    """
    配置 WARP 出站规则

    Args:
        warp_mode: WARP 模式 (sx/xs/s/s4/s6/x/x4/x6)

    Returns:
        dict: 包含各种配置信息的字典
    """
    v4 = read_file(os.path.join(AGSBX_DATA, "common", "v4"))
    v6 = read_file(os.path.join(AGSBX_DATA, "common", "v6"))

    # 判断是否使用 direct
    if v6.startswith("2a09") or v4.startswith("104.28"):
        s1outtag = "direct"
        s2outtag = "direct"
        x1outtag = "direct"
        x2outtag = "direct"
        xip = '"::/0", "0.0.0.0/0"'
        sip = '"::/0", "0.0.0.0/0"'
        warp_mode = "warpargo"
    else:
        warp_modes = {
            "": ("warp-out", "warp-out", "warp-out", "warp-out"),
            "sx": ("warp-out", "warp-out", "warp-out", "warp-out"),
            "xs": ("warp-out", "warp-out", "warp-out", "warp-out"),
            "s": ("warp-out", "warp-out", "direct", "direct"),
            "s4": ("warp-out", "direct", "direct", "direct"),
            "s6": ("warp-out", "direct", "direct", "direct"),
            "x": ("direct", "direct", "warp-out", "warp-out"),
            "x4": ("direct", "direct", "warp-out", "direct"),
            "x6": ("direct", "direct", "warp-out", "direct"),
        }

        mode_config = warp_modes.get(
            warp_mode, ("direct", "direct", "direct", "direct")
        )
        s1outtag, s2outtag, x1outtag, x2outtag = mode_config

        if warp_mode == "s4":
            xip = '"::/0", "0.0.0.0/0"'
            sip = '"0.0.0.0/0"'
        elif warp_mode == "s6":
            xip = '"::/0", "0.0.0.0/0"'
            sip = '"::/0"'
        elif warp_mode == "x4":
            xip = '"0.0.0.0/0"'
            sip = '"::/0", "0.0.0.0/0"'
        elif warp_mode == "x6":
            xip = '"::/0"'
            sip = '"::/0", "0.0.0.0/0"'
        else:
            xip = '"::/0", "0.0.0.0/0"'
            sip = '"::/0", "0.0.0.0/0"'

    # 保存标签配置
    write_file(os.path.join(AGSBX_DATA, "common", "s1outtag"), s1outtag)
    write_file(os.path.join(AGSBX_DATA, "common", "s2outtag"), s2outtag)
    write_file(os.path.join(AGSBX_DATA, "common", "x1outtag"), x1outtag)
    write_file(os.path.join(AGSBX_DATA, "common", "x2outtag"), x2outtag)
    write_file(os.path.join(AGSBX_DATA, "common", "xip"), xip)
    write_file(os.path.join(AGSBX_DATA, "common", "sip"), sip)

    # 判断 IPv4/IPv6 支持情况
    v46url = "https://icanhazip.com"
    v4_ok = False
    v6_ok = False

    if has_command("curl"):
        rc1, _, _ = run_command(["curl", "-s4m5", "-k", v46url])
        rc2, _, _ = run_command(["curl", "-s6m5", "-k", v46url])
        v4_ok = rc1 == 0
        v6_ok = rc2 == 0
    elif has_command("wget"):
        rc1, _, _ = run_command(["wget", "-4", "--tries=2", "-qO-", v46url])
        rc2, _, _ = run_command(["wget", "-6", "--tries=2", "-qO-", v46url])
        v4_ok = rc1 == 0
        v6_ok = rc2 == 0

    if v4_ok and v6_ok:
        if "s4" in warp_mode:
            sbyx = "prefer_ipv4"
        else:
            sbyx = "prefer_ipv6"

        if "x4" in warp_mode:
            xryx = "ForceIPv4v6"
        elif "x" in warp_mode:
            xryx = "ForceIPv6v4"
        else:
            xryx = "ForceIPv4v6"
    elif v4_ok and not v6_ok:
        if "s4" in warp_mode:
            sbyx = "ipv4_only"
        else:
            sbyx = "prefer_ipv6"

        if "x4" in warp_mode:
            xryx = "ForceIPv4"
        elif "x" in warp_mode:
            xryx = "ForceIPv6v4"
        else:
            xryx = "ForceIPv4v6"
    else:
        sbyx = "prefer_ipv4"
        xryx = "ForceIPv6v4"

    if "x4" in warp_mode:
        wxryx = "ForceIPv4"
    elif "x6" in warp_mode:
        wxryx = "ForceIPv6"
    else:
        wxryx = "ForceIPv6v4"

    write_file(os.path.join(AGSBX_DATA, "common", "wxryx"), wxryx)
    write_file(os.path.join(AGSBX_DATA, "common", "sbyx"), sbyx)
    write_file(os.path.join(AGSBX_DATA, "common", "xryx"), xryx)

    return {
        "s1outtag": s1outtag,
        "s2outtag": s2outtag,
        "x1outtag": x1outtag,
        "x2outtag": x2outtag,
        "xip": xip,
        "sip": sip,
        "sbyx": sbyx,
        "xryx": xryx,
    }


def get_uuid(existing_uuid: str = "") -> str:
    """
    获取或生成 UUID

    Args:
        existing_uuid: 现有的 UUID（可选）

    Returns:
        str: UUID 字符串
    """
    uuid_file = os.path.join(AGSBX_DATA, "common", "uuid")

    if existing_uuid:
        uuid = existing_uuid
    elif os.path.exists(uuid_file):
        uuid = read_file(uuid_file)
        if uuid:
            return uuid

    if not existing_uuid:
        sb_core = os.path.join(AGSBX_HOME, "sing-box")
        uuid = ""

        if os.path.exists(sb_core):
            try:
                result = subprocess.run(
                    [sb_core, "generate", "uuid"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                uuid = result.stdout.strip()
                if not uuid:
                    uuid = str(uuid_lib.uuid4())
            except Exception:
                uuid = str(uuid_lib.uuid4())
        else:
            uuid = str(uuid_lib.uuid4())

    write_file(uuid_file, uuid)
    return uuid


def generate_rand_port(port_file: str, specified_port: str = "") -> int:
    """
    生成随机端口或使用指定的端口

    Args:
        port_file: 端口文件路径
        specified_port: 指定的端口号（可选，"auto" 表示随机生成）

    Returns:
        int: 端口号
    """
    # 被限制的端口列表（云服务商可能封锁）
    blocked_ports = {
        22,
        23,
        25,
        53,
        80,
        110,
        143,
        443,
        465,
        587,
        993,
        995,
        1433,
        1434,
        3306,
        3389,
        5432,
        6379,
        8080,
        8443,
        8888,
        9000,
    }

    # 如果指定了端口且不是 "auto"，直接使用指定端口
    if specified_port and specified_port != "auto":
        port = int(specified_port)
        write_file(port_file, str(port))
        return port

    # 如果端口文件已存在，读取已保存的端口
    if os.path.exists(port_file):
        saved_port = read_file(port_file)
        if saved_port:
            return int(saved_port)

    # 生成随机端口，避开被限制的端口
    while True:
        port = random.randint(10000, 65535)
        if port not in blocked_ports:
            break
    write_file(port_file, str(port))
    return port


def download_binary(url: str, out_path: str) -> bool:
    """
    下载二进制文件

    Args:
        url: 下载 URL
        out_path: 输出路径

    Returns:
        bool: 下载是否成功
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if has_command("curl"):
        rc, stdout, stderr = run_command(
            ["curl", "-L", "-o", out_path, "-#", "--retry", "3", "-f", url], timeout=120
        )
    elif has_command("wget"):
        rc, stdout, stderr = run_command(
            ["wget", "-O", out_path, "--tries=3", url], timeout=120
        )
    else:
        print("错误: curl 或 wget 均不可用")
        return False

    if os.path.exists(out_path):
        file_size = os.path.getsize(out_path)
        if file_size < 1000:
            print(f"错误: 下载的文件过小 ({file_size} bytes)，可能是 404 页面")
            try:
                os.remove(out_path)
            except Exception:
                pass
            return False
        os.chmod(out_path, 0o755)
        print(f"下载完成: {out_path} ({file_size} bytes)")
        return True

    print(f"下载失败: {stderr}")
    return False


def get_server_ip(ippz: str = "") -> str:
    """
    获取服务器 IP 地址

    Args:
        ippz: IP 版本偏好 (4/6/空)

    Returns:
        str: 服务器 IP 地址
    """
    v4 = read_file(os.path.join(AGSBX_DATA, "common", "v4"))
    v6 = read_file(os.path.join(AGSBX_DATA, "common", "v6"))

    if not v4 and not v6:
        v4v6_main()
        v4 = read_file(os.path.join(AGSBX_DATA, "common", "v4"))
        v6 = read_file(os.path.join(AGSBX_DATA, "common", "v6"))

    if ippz == "4":
        if v4:
            server_ip = v4
        else:
            v4v6_main()
            server_ip = read_file(os.path.join(AGSBX_DATA, "common", "v4"))
    elif ippz == "6":
        if v6:
            server_ip = f"[{v6}]"
        else:
            v4v6_main()
            v6 = read_file(os.path.join(AGSBX_DATA, "common", "v6"))
            server_ip = f"[{v6}]"
    else:
        if v4:
            server_ip = v4
        elif v6:
            server_ip = f"[{v6}]"
        else:
            v4v6_main()
            v4 = read_file(os.path.join(AGSBX_DATA, "common", "v4"))
            v6 = read_file(os.path.join(AGSBX_DATA, "common", "v6"))
            server_ip = v4 if v4 else f"[{v6}]"

    write_file(os.path.join(AGSBX_DATA, "common", "server_ip"), server_ip)
    return server_ip


def install_systemd_service(
    service_name: str, exec_start: str, description: str = ""
) -> bool:
    """
    安装系统服务

    Args:
        service_name: 服务名称
        exec_start: 启动命令
        description: 服务描述

    Returns:
        bool: 安装是否成功
    """
    # 检查是否在容器环境中（多种检测方式）
    in_container = (
        os.path.exists("/.dockerenv")
        or os.path.exists("/run/.containerenv")
        or os.path.exists("/.dockerinit")
        or os.path.exists("/proc/1/cgroup")
    )

    # 检查 systemd 是否真正可用
    systemd_available = False
    try:
        result = subprocess.run(
            ["systemctl", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        systemd_available = result.returncode == 0
    except Exception:
        pass

    # 非 root 用户、容器环境、或 systemd 不可用时，使用后台运行
    if os.geteuid() != 0 or in_container or not systemd_available:
        try:
            # 定义日志文件路径
            log_file = os.path.join(AGSBX_HOME, "sb.log")
            
            # 使用 nohup 保护进程，输出重定向到日志文件
            cmd = f"nohup {exec_start} >> {log_file} 2>&1 &"
            print(f"[DEBUG] 启动命令: {cmd}")
            print(f"[DEBUG] 日志文件: {log_file}")
            
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                cwd=AGSBX_HOME,
            )
            print(f"[DEBUG] Popen 返回的 PID: {process.pid}")

            # 等待一下确认进程启动
            import time
            time.sleep(2)

            # 检查 nohup 进程本身状态
            if process.poll() is None:
                print("[DEBUG] nohup 命令已执行，进程处于运行状态")
            else:
                stdout, stderr = process.communicate()
                print(f"[DEBUG] nohup 命令已退出，返回码: {process.returncode}")
                if stdout:
                    print(f"[DEBUG] stdout: {stdout.decode() if isinstance(stdout, bytes) else stdout}")
                if stderr:
                    print(f"[DEBUG] stderr: {stderr.decode() if isinstance(stderr, bytes) else stderr}")

            # 使用 pgrep 检查 sing-box 进程是否真的在运行
            check_cmd = ["pgrep", "-f", "sing-box run"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            if result.stdout:
                pids = result.stdout.strip().split("\n")
                print(f"[DEBUG] 找到 sing-box 进程 PID: {pids}")
                print("✅ 后台进程运行中")
            else:
                print("[DEBUG] 未找到 sing-box 进程")
                print("⚠️ 警告: 进程可能未启动成功")

            # 显示日志文件内容（如果存在）
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    log_content = f.read()
                if log_content:
                    print(f"[DEBUG] 日志内容:\n{log_content[:500]}")
                else:
                    print("[DEBUG] 日志文件为空")
            
            return True
        except Exception as e:
            print(f"启动进程失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    if subprocess.run(["pidof", "systemd"], capture_output=True).returncode == 0:
        service_file = f"/etc/systemd/system/{service_name}.service"
        service_content = f"""[Unit]
Description={description or f"{service_name} service"}
After=network.target

[Service]
Type=simple
NoNewPrivileges=yes
TimeoutStartSec=0
ExecStart={exec_start}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        with open(service_file, "w") as f:
            f.write(service_content)

        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "enable", service_name], capture_output=True)
        subprocess.run(["systemctl", "start", service_name], capture_output=True)
        return True

    if shutil.which("rc-service"):
        initd_file = f"/etc/init.d/{service_name}"
        initd_content = f"""#!/sbin/openrc-run
description="{description or f"{service_name} service"}"
command="/bin/sh"
command_args="-c '{exec_start}'"
command_background=yes
pidfile="/run/{service_name}.pid"

depend() {{
need net
}}
"""
        with open(initd_file, "w") as f:
            f.write(initd_content)
        os.chmod(initd_file, 0o755)

        subprocess.run(
            ["rc-update", "add", service_name, "default"], capture_output=True
        )
        subprocess.run(["rc-service", service_name, "start"], capture_output=True)
        return True

    # 默认使用后台运行
    try:
        # 定义日志文件路径
        log_file = os.path.join(AGSBX_HOME, "sb.log")
        
        # 使用 nohup 保护进程，输出重定向到日志文件
        cmd = f"nohup {exec_start} >> {log_file} 2>&1 &"
        print(f"[DEBUG] 默认启动命令: {cmd}")
        print(f"[DEBUG] 日志文件: {log_file}")
        
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        print(f"[DEBUG] Popen 返回的 PID: {process.pid}")

        import time
        time.sleep(2)

        # 检查 nohup 进程状态
        if process.poll() is None:
            print("[DEBUG] nohup 命令已执行，进程处于运行状态")
        else:
            stdout, stderr = process.communicate()
            print(f"[DEBUG] nohup 命令已退出，返回码: {process.returncode}")

        # 使用 pgrep 检查 sing-box 进程
        check_cmd = ["pgrep", "-f", "sing-box run"]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.stdout:
            pids = result.stdout.strip().split("\n")
            print(f"[DEBUG] 找到 sing-box 进程 PID: {pids}")
            print("✅ 后台进程运行中")
        else:
            print("[DEBUG] 未找到 sing-box 进程")
            print("⚠️ 警告: 进程可能未启动成功")

        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log_content = f.read()
            if log_content:
                print(f"[DEBUG] 日志内容:\n{log_content[:500]}")
            else:
                print("[DEBUG] 日志文件为空")
        
        return True
    except Exception as e:
        print(f"启动进程失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def stop_service(service_name: str, binary_name: str) -> None:
    """
    停止服务

    Args:
        service_name: 服务名称
        binary_name: 二进制文件名称
    """
    # 杀死进程
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"agsbx/{binary_name}"], capture_output=True, text=True
        )
        if result.stdout:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    os.kill(int(pid), 15)  # SIGTERM
                except (ProcessLookupError, ValueError):
                    pass
    except Exception:
        pass

    if os.geteuid() != 0:
        return

    # 检查 systemd
    if subprocess.run(["pidof", "systemd"], capture_output=True).returncode == 0:
        subprocess.run(["systemctl", "stop", service_name], capture_output=True)
        subprocess.run(["systemctl", "disable", service_name], capture_output=True)

    # 检查 OpenRC
    elif shutil.which("rc-service"):
        subprocess.run(["rc-service", service_name, "stop"], capture_output=True)
        subprocess.run(
            ["rc-update", "del", service_name, "default"], capture_output=True
        )


def get_reality_domain(reym: str = "") -> str:
    """
    获取 REAITY 域名

    Args:
        reym: 指定的域名（可选）

    Returns:
        str: 域名
    """
    if reym:
        return reym

    domain_file = os.path.join(AGSBX_DATA, "common", "ym_vl_re")
    if os.path.exists(domain_file):
        return read_file(domain_file)

    return "apple.com"


def save_reality_domain(reym: str = "") -> str:
    """
    保存 REAITY 域名

    Args:
        reym: 指定的域名（可选）

    Returns:
        str: 保存的域名
    """
    domain = get_reality_domain(reym)
    write_file(os.path.join(AGSBX_DATA, "common", "ym_vl_re"), domain)
    return domain


def get_cdn_domain(cdnym: str = "") -> str:
    """
    获取 CDN 域名

    Args:
        cdnym: 指定的域名（可选）

    Returns:
        str: CDN 域名
    """
    if cdnym:
        write_file(os.path.join(AGSBX_DATA, "common", "cdnym"), cdnym)
        return cdnym

    cdn_file = os.path.join(AGSBX_DATA, "common", "cdnym")
    if os.path.exists(cdn_file):
        return read_file(cdn_file)

    return ""


def check_process_running(process_name: str) -> bool:
    """
    检查进程是否在运行

    Args:
        process_name: 进程名称

    Returns:
        bool: 进程是否在运行
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_name], capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_hostname() -> str:
    """
    获取主机名

    Returns:
        str: 主机名
    """
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


# ============================================================================
# Sing-box 部署相关函数
# ============================================================================

# 路径定义
SB_DATA = os.path.join(AGSBX_DATA, "singbox")
SB_CORE = os.path.join(AGSBX_HOME, "sing-box")
SB_CONFIG = os.path.join(AGSBX_HOME, "sb.json")

# 确保目录存在
os.makedirs(AGSBX_HOME, exist_ok=True)
os.makedirs(SB_DATA, exist_ok=True)
os.makedirs(os.path.join(AGSBX_DATA, "common"), exist_ok=True)


def show_usage():
    """显示使用说明"""
    print("Sing-box 内核独立部署脚本")
    print("")
    print("用法: python app.py [命令] [参数]")
    print("")
    print("命令:")
    print("  install/i         安装 Sing-box 内核")
    print("  upsingbox/ups/u   更新 Sing-box 内核")
    print("  restart/res/r     重启 Sing-box 服务")
    print("  stop               停止 Sing-box 服务")
    print("  status/stat/s      查看 Sing-box 运行状态")
    print("  list/l             显示节点配置")
    print("  del/uninstall/d    卸载 Sing-box")
    print("")
    print("协议变量 (安装时使用):")
    print("  hypt=X             Hysteria2 (端口)")
    print("  tupt=X             Tuic (端口)")
    print("  anpt=X            Anytls (端口)")
    print("  arpt=X            Any-Reality (端口)")
    print("  sspt=X            Shadowsocks-2022 (端口)")
    print("  vmpt=X            Vmess-ws (端口)")
    print("  sopt=X            Socks5 (端口)")
    print("  DOMAIN=域名        【仅容器类docker】启用vless-ws-tls (服务器域名)")
    print("  uuid=UUID          指定UUID (用于固定密码)")
    print("")
    print("示例:")
    print("  hypt=443 python app.py install    # 安装 Hysteria2 协议")
    print("  tupt=443 python app.py install    # 安装 Tuic 协议")
    print("  python app.py list                 # 显示节点配置")


def check_installed() -> bool:
    """检查 Sing-box 是否已安装"""
    return os.path.exists(SB_CORE)


def get_singbox_version() -> str:
    """获取 Sing-box 版本"""
    if not os.path.exists(SB_CORE):
        return ""

    try:
        result = subprocess.run(
            [SB_CORE, "version"], capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr

        for line in output.split("\n"):
            line = line.strip()
            if "version" in line.lower():
                parts = line.split()
                for part in parts:
                    if re.match(r"^\d+\.\d+", part):
                        return part
                if parts:
                    return parts[-1]

        if output.strip():
            return output.strip().split()[0] if output.strip() else ""

    except Exception as e:
        print(f"获取版本失败: {e}")

    return ""


def install_singbox(
    hypt: str = "",
    tupt: str = "",
    anpt: str = "",
    arpt: str = "",
    sspt: str = "",
    vmpt: str = "",
    sopt: str = "",
    warp: str = "sx",
    DOMAIN: str = "",
    uuid: str = "",
) -> None:
    """
    安装 Sing-box 内核

    Args:
        hypt: Hysteria2 端口
        tupt: Tuic 端口
        anpt: AnyTLS 端口
        arpt: Any-Reality 端口
        sspt: Shadowsocks-2022 端口
        vmpt: Vmess-ws 端口
        sopt: Socks5 端口
        warp: WARP 模式
        DOMAIN: 服务器域名，启用 vless-ws-tls
        uuid: 自定义 UUID
    """
    print("=========启用Sing-box内核=========")

    # 获取服务器 IP 信息（用于判断 IPv6 支持）
    print("获取服务器 IP 信息...")
    v4v6_main()

    # 先停止已存在的进程
    if check_process_running("sing-box"):
        print("停止已存在的 sing-box 进程...")
        try:
            subprocess.run(["pkill", "-f", "sing-box"], capture_output=True)
            import time

            time.sleep(1)
        except Exception:
            pass

    # 获取系统架构
    cpu = get_arch()

    # 下载 Sing-box 内核
    if not os.path.exists(SB_CORE):
        url = f"https://github.com/yonggekkk/argosbx/releases/download/argosbx/sing-box-{cpu}"
        print(f"正在下载 Sing-box 内核 (架构: {cpu})...")
        print(f"URL: {url}")
        success = download_binary(url, SB_CORE)
        if not success:
            print("错误: 下载失败，请检查网络连接")
            print("提示: 可以手动下载内核文件到 ~/app/sing-box")
            return

    # 检查安装
    if not os.path.exists(SB_CORE):
        print(f"错误: Sing-box 内核不存在: {SB_CORE}")
        return

    # 确保内核有执行权限
    st = os.stat(SB_CORE)
    print(f"内核文件大小: {st.st_size} bytes")
    print(f"内核文件权限: {oct(st.st_mode)}")

    # 检查并修复执行权限
    if not os.access(SB_CORE, os.X_OK):
        print("修复内核执行权限...")
        os.chmod(SB_CORE, 0o755)
        st = os.stat(SB_CORE)
        print(f"修复后权限: {oct(st.st_mode)}")

    # 测试内核是否可执行
    version = get_singbox_version()
    if not version:
        print("警告: 无法获取版本信息，尝试直接运行...")
        try:
            result = subprocess.run(
                [SB_CORE, "version"], capture_output=True, text=True, timeout=10
            )
            print(f"stdout: {result.stdout[:500] if result.stdout else '(空)'}")
            print(f"stderr: {result.stderr[:500] if result.stderr else '(空)'}")
            print(f"returncode: {result.returncode}")

            # 检查是否是段错误（架构不匹配）
            if result.returncode == -11 or result.returncode == -6:
                print("")
                print("错误: 内核执行失败（段错误），可能是架构不匹配")
                print("尝试下载其他架构的内核...")

                # 尝试另一种架构
                other_arch = "arm64" if cpu == "amd64" else "amd64"
                print(f"当前架构: {cpu}，尝试: {other_arch}")

                # 删除旧内核
                os.remove(SB_CORE)

                # 下载新架构内核
                url = f"https://github.com/yonggekkk/argosbx/releases/download/argosbx/sing-box-{other_arch}"
                print(f"URL: {url}")
                success = download_binary(url, SB_CORE)
                if success:
                    version = get_singbox_version()
                    if version:
                        print(f"Sing-box 内核版本: {version}")
                    else:
                        print("错误: 两种架构都无法运行，请检查系统环境")
                        print("提示: 运行 'uname -m' 查看系统架构")
                        print("提示: 运行 'ldd ~/app/sing-box' 查看依赖")
                        return
                else:
                    print("错误: 下载失败")
                    return
            else:
                print("可能原因: 缺少依赖库或权限问题")
                print("提示: 运行 'ldd ~/app/sing-box' 查看依赖")
                return
        except Exception as e:
            print(f"执行错误: {e}")
            print("可能原因: 架构不匹配或缺少依赖库")
            return
    else:
        print(f"Sing-box 内核版本: {version}")

    # 创建 keys 目录
    keys_dir = os.path.join(SB_DATA, "keys")
    os.makedirs(keys_dir, exist_ok=True)

    # 生成或获取 UUID
    uuid_val = get_uuid(uuid)
    write_file(os.path.join(AGSBX_DATA, "common", "uuid"), uuid_val)
    print(f"UUID: {uuid_val}")

    # 生成 TLS 证书
    private_key_path = os.path.join(AGSBX_HOME, "private.key")
    cert_path = os.path.join(AGSBX_HOME, "cert.pem")

    # 尝试用 openssl 生成证书
    if has_command("openssl"):
        # 生成私钥
        rc1, _, err1 = run_command(
            [
                "openssl",
                "ecparam",
                "-genkey",
                "-name",
                "prime256v1",
                "-out",
                private_key_path,
            ]
        )
        if rc1 == 0 and os.path.exists(private_key_path):
            # 生成证书
            rc2, _, err2 = run_command(
                [
                    "openssl",
                    "req",
                    "-new",
                    "-x509",
                    "-days",
                    "36500",
                    "-key",
                    private_key_path,
                    "-out",
                    cert_path,
                    "-subj",
                    "/CN=www.bing.com",
                ]
            )
            if rc2 == 0 and os.path.exists(cert_path):
                print("TLS 证书生成成功")

    # 如果证书生成失败，下载默认证书
    if not os.path.exists(private_key_path):
        url = (
            "https://github.com/yonggekkk/argosbx/releases/download/argosbx/private.key"
        )
        print("下载默认私钥...")
        download_binary(url, private_key_path)

    if not os.path.exists(cert_path):
        url = "https://github.com/yonggekkk/argosbx/releases/download/argosbx/cert.pem"
        print("下载默认证书...")
        download_binary(url, cert_path)

    # 最终检查
    if not os.path.exists(private_key_path) or not os.path.exists(cert_path):
        print("错误: 证书文件缺失，无法启动服务")
        return

    # 构建配置 JSON
    config: Dict[str, Any] = {
        "log": {"disabled": False, "level": "info", "timestamp": True},
        "inbounds": [],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }

    inbounds = []
    port_hy2 = 0

    # 如果没有指定任何协议端口，提示用户并退出
    if not any([hypt, tupt, anpt, arpt, sspt, vmpt, sopt, DOMAIN, uuid]):
        print("未指定任何协议端口，请至少指定一个协议端口")
        print("用法:")
        print("  hypt=端口 python app.py install    # 安装 Hysteria2 协议")
        print("  tupt=端口 python app.py install    # 安装 Tuic 协议")
        print("  或者同时指定多个协议")
        return

    # Hysteria2 配置
    if hypt:
        port_hy2 = generate_rand_port(os.path.join(SB_DATA, "port_hy2"), hypt)
        print(f"Hysteria2 端口: {port_hy2}")
        inbounds.append(
            {
                "type": "hysteria2",
                "tag": "hy2-sb",
                "listen": "::",
                "listen_port": port_hy2,
                "users": [{"password": uuid_val}],
                "ignore_client_bandwidth": False,
                "tls": {
                    "enabled": True,
                    "alpn": ["h3"],
                    "certificate_path": cert_path,
                    "key_path": private_key_path,
                },
            }
        )

    # Tuic 配置
    if tupt:
        port_tu = generate_rand_port(os.path.join(SB_DATA, "port_tu"), tupt)
        print(f"Tuic 端口: {port_tu}")
        inbounds.append(
            {
                "type": "tuic",
                "tag": "tuic5-sb",
                "listen": "::",
                "listen_port": port_tu,
                "users": [{"uuid": uuid_val, "password": uuid_val}],
                "congestion_control": "bbr",
                "tls": {
                    "enabled": True,
                    "alpn": ["h3"],
                    "certificate_path": cert_path,
                    "key_path": private_key_path,
                },
            }
        )

    # AnyTLS 配置
    if anpt:
        port_an = generate_rand_port(os.path.join(SB_DATA, "port_an"), anpt)
        print(f"Anytls 端口: {port_an}")
        inbounds.append(
            {
                "type": "anytls",
                "tag": "anytls-sb",
                "listen": "::",
                "listen_port": port_an,
                "users": [{"password": uuid_val}],
                "padding_scheme": [],
                "tls": {
                    "enabled": True,
                    "certificate_path": cert_path,
                    "key_path": private_key_path,
                },
            }
        )

    # Any-Reality 配置
    if arpt:
        ym_vl_re = save_reality_domain()
        print(f"Reality 域名: {ym_vl_re}")

        # 生成或读取 Reality 密钥对
        private_key_file = os.path.join(keys_dir, "private_key")
        public_key_file = os.path.join(keys_dir, "public_key")
        short_id_file = os.path.join(keys_dir, "short_id")

        if not os.path.exists(private_key_file):
            rc, output, stderr = run_command([SB_CORE, "generate", "reality-keypair"])
            if rc == 0 and output.strip():
                key_pair = {}
                for line in output.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key_name = key.strip().lower().replace('privatekey', 'private_key').replace('publickey', 'public_key')
                        key_pair[key_name] = value.strip()
            elif rc == 0 and stderr.strip():
                key_pair = {}
                for line in stderr.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key_name = key.strip().lower().replace('privatekey', 'private_key').replace('publickey', 'public_key')
                        key_pair[key_name] = value.strip()
            else:
                print("错误: 生成 Reality 密钥对失败")
                print(f"返回码: {rc}, stdout: {output}, stderr: {stderr}")
                raise RuntimeError("无法生成 Reality 密钥对")
            private_key_s = key_pair.get("private_key", "")
            public_key_s = key_pair.get("public_key", "")

            rc, short_id_out, _ = run_command(
                [SB_CORE, "generate", "rand", "--hex", "4"]
            )
            short_id_s = short_id_out.strip() if short_id_out else "0000"

            write_file(private_key_file, private_key_s)
            write_file(public_key_file, public_key_s)
            write_file(short_id_file, short_id_s)

        private_key_s = read_file(private_key_file)
        public_key_s = read_file(public_key_file)
        short_id_s = read_file(short_id_file)

        port_ar = generate_rand_port(os.path.join(SB_DATA, "port_ar"), arpt)
        print(f"Any-Reality 端口: {port_ar}")
        inbounds.append(
            {
                "type": "anytls",
                "tag": "anyreality-sb",
                "listen": "::",
                "listen_port": port_ar,
                "users": [{"password": uuid_val}],
                "padding_scheme": [],
                "tls": {
                    "enabled": True,
                    "server_name": ym_vl_re,
                    "reality": {
                        "enabled": True,
                        "handshake": {"server": ym_vl_re, "server_port": 443},
                        "private_key": private_key_s,
                        "short_id": [short_id_s],
                    },
                },
            }
        )

    # Shadowsocks-2022 配置
    if sspt:
        sskey_file = os.path.join(SB_DATA, "sskey")
        if not os.path.exists(sskey_file):
            rc, output, _ = run_command([SB_CORE, "generate", "rand", "16", "--base64"])
            if rc == 0:
                sskey = output.strip()
            else:
                # 使用 Python 生成
                sskey = base64.b64encode(os.urandom(16)).decode()
            write_file(sskey_file, sskey)

        sskey = read_file(sskey_file)
        port_ss = generate_rand_port(os.path.join(SB_DATA, "port_ss"), sspt)
        print(f"Shadowsocks-2022 端口: {port_ss}")
        inbounds.append(
            {
                "type": "shadowsocks",
                "tag": "ss-2022",
                "listen": "::",
                "listen_port": port_ss,
                "method": "2022-blake3-aes-128-gcm",
                "password": sskey,
            }
        )

    # Vmess-ws 配置
    if vmpt:
        port_vm_ws = generate_rand_port(os.path.join(SB_DATA, "port_vm_ws"), vmpt)
        print(f"Vmess-ws 端口: {port_vm_ws}")
        inbounds.append(
            {
                "type": "vmess",
                "tag": "vmess-sb",
                "listen": "::",
                "listen_port": port_vm_ws,
                "users": [{"uuid": uuid_val, "alterId": 0}],
                "transport": {
                    "type": "ws",
                    "path": f"{uuid_val}-vm",
                    "max_early_data": 2048,
                    "early_data_header_name": "Sec-WebSocket-Protocol",
                },
            }
        )

    # Socks5 配置
    if sopt:
        port_so = generate_rand_port(os.path.join(SB_DATA, "port_so"), sopt)
        print(f"Socks5 端口: {port_so}")
        inbounds.append(
            {
                "tag": "socks5-sb",
                "type": "socks",
                "listen": "::",
                "listen_port": port_so,
                "users": [{"username": uuid_val, "password": uuid_val}],
            }
        )

    # Vless-ws-tls 配置
    if DOMAIN:
        port_vl_ws_tls = 443
        write_file(os.path.join(SB_DATA, "port_vl_ws_tls"), "443")
        print(f"Vless-ws-tls 端口: {port_vl_ws_tls}")
        print(f"服务器域名: {DOMAIN}")
        inbounds.append(
            {
                "type": "vless",
                "tag": "vless-ws-tls-sb",
                "listen": "::",
                "listen_port": port_vl_ws_tls,
                "users": [{"uuid": uuid_val}],
                "transport": {
                    "type": "ws",
                    "path": f"/{uuid_val}-vl",
                    "max_early_data": 2048,
                    "early_data_header_name": "Sec-WebSocket-Protocol",
                },
                "tls": {
                    "enabled": True,
                    "server_name": DOMAIN,
                    "certificate_path": cert_path,
                    "key_path": private_key_path,
                },
            }
        )
        write_file(os.path.join(SB_DATA, "domain"), DOMAIN)

    config["inbounds"] = inbounds

    # WARP 配置
    check_warp()
    config_warp_outbound(warp)

    # 读取 WARP 配置
    pvk = read_file(os.path.join(AGSBX_DATA, "common", "warp_private_key"))
    wpv6 = read_file(os.path.join(AGSBX_DATA, "common", "warp_ipv6"))
    res_str = read_file(os.path.join(AGSBX_DATA, "common", "warp_reserved"))
    s1outtag = read_file(os.path.join(AGSBX_DATA, "common", "s1outtag"))
    s2outtag = read_file(os.path.join(AGSBX_DATA, "common", "s2outtag"))
    sip = read_file(os.path.join(AGSBX_DATA, "common", "sip"))

    # 处理 reserved
    try:
        res = json.loads(res_str) if res_str else [0, 0, 0]
    except json.JSONDecodeError:
        res = [0, 0, 0]

    # 如果 WARP 配置不完整，使用默认值
    if not pvk:
        pvk = "52cuYFgCJXp0LAq7+nWJIbCXXgU9eGggOc+Hlfz5u6A="
    if not wpv6:
        wpv6 = "2606:4700:110:8d8d:1845:c39f:2dd5:a03a"
    if not res or res == [0, 0, 0]:
        res = [215, 69, 233]

    # 检查服务器是否有 IPv6，决定 WARP 连接地址
    v6 = read_file(os.path.join(AGSBX_DATA, "common", "v6"))
    if v6:
        # 有 IPv6，使用 IPv6 连接 WARP
        sendip = "2606:4700:d0::a29f:c001"
    else:
        # 无 IPv6，使用 IPv4 连接 WARP
        sendip = "162.159.192.1"

    # 构建 WARP 地址列表
    warp_addresses = ["172.16.0.2/32", f"{wpv6}/128"]

    # 添加 endpoints 和 route
    config["endpoints"] = [
        {
            "type": "wireguard",
            "tag": "warp-out",
            "address": warp_addresses,
            "private_key": pvk,
            "peers": [
                {
                    "address": sendip,
                    "port": 2408,
                    "public_key": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
                    "allowed_ips": ["0.0.0.0/0", "::/0"],
                    "reserved": res,
                }
            ],
        }
    ]

    # 解析 sip 为列表格式
    if not sip:
        sip_list = ["::/0", "0.0.0.0/0"]
    else:
        # 尝试解析 JSON 格式的字符串
        try:
            # 移除多余的引号，尝试解析
            sip_clean = sip.strip('"').strip("'")
            if sip_clean.startswith("["):
                sip_list = json.loads(sip_clean)
            else:
                # 格式如: "::/0", "0.0.0.0/0"
                sip_list = [
                    s.strip().strip('"').strip("'") for s in sip.split(",") if s.strip()
                ]
        except Exception:
            sip_list = ["::/0", "0.0.0.0/0"]

    # 默认使用 direct 出站（与原始脚本一致）
    final_outbound = s2outtag if s2outtag else "direct"
    ip_cidr_outbound = s1outtag if s1outtag else "direct"

    config["route"] = {
        "rules": [
            {"action": "sniff"},
            {"action": "resolve", "strategy": "prefer_ipv6"},
            {"ip_cidr": sip_list, "outbound": ip_cidr_outbound},
        ],
        "final": final_outbound,
    }

    # 写入配置文件
    with open(SB_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

    # 安装系统服务
    exec_cmd = f"{SB_CORE} run -c {SB_CONFIG}"
    print(f"启动命令: {exec_cmd}")
    install_systemd_service("sb", exec_cmd, "Sing-box service")

    # 等待一下让服务启动
    import time

    time.sleep(3)

    # 检查服务是否运行
    if check_process_running("sing-box"):
        print("状态: 服务已启动")
        # 显示监听端口（兼容不同环境）
        try:
            # 尝试 ss 命令
            result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                print("监听端口:")
                for line in result.stdout.split("\n"):
                    if "sing-box" in line or (port_hy2 > 0 and str(port_hy2) in line):
                        print(f"  {line}")
            else:
                # 尝试 netstat 命令
                result = subprocess.run(
                    ["netstat", "-tlnp"], capture_output=True, text=True
                )
                if result.returncode == 0 and result.stdout:
                    print("监听端口:")
                    for line in result.stdout.split("\n"):
                        if "sing-box" in line or (
                            port_hy2 > 0 and str(port_hy2) in line
                        ):
                            print(f"  {line}")
        except Exception:
            pass
    else:
        print("警告: 服务启动失败，请检查日志")
        # 尝试直接运行查看错误
        print("尝试直接运行查看错误...")
        try:
            result = subprocess.run(
                [SB_CORE, "run", "-c", SB_CONFIG],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stderr:
                print(f"错误输出: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("服务运行中（超时检测）")
        except Exception as e:
            print(f"运行错误: {e}")

    print("Sing-box 安装完成")
    print("")

    # 显示节点信息
    show_links()

    # 检测是否在容器环境中
    in_container = (
        os.path.exists("/.dockerenv")
        or os.path.exists("/run/.containerenv")
        or os.path.exists("/.dockerinit")
    )

    # 容器环境中启动 HTTP 服务器和生成节点信息
    if in_container:
        server_port = int(os.environ.get("PORT", "3000"))
        server_domain = os.environ.get("DOMAIN", "")
        
        # 确保 server_ip 已定义
        if 'server_ip' not in dir() or not server_ip:
            server_ip = get_server_ip()
        
        print(f"[DEBUG] HTTP 服务器配置: port={server_port}, domain={server_domain}, ip={server_ip}")

        nodes_content = generate_nodes_text(uuid_val, server_ip, server_domain)
        nodes_file = os.path.join(AGSBX_DATA, "nodes.txt")
        write_file(nodes_file, nodes_content)
        
        print(f"[DEBUG] 节点文件已生成: {nodes_file}")

        start_http_server(server_port, server_domain, uuid_val)

    # 在容器中，保持主进程运行以防止容器退出
    if in_container:
        print("\n========== 容器环境保持运行 ==========")
        print(f"HTTP 服务器运行在端口: {server_port}")
        print(f"访问节点信息: http://服务器IP:{server_port}/{uuid_val}")
        print("进程在后台持续运行中...")
        print(f"日志文件: {os.path.join(AGSBX_HOME, 'sb.log')}")
        print("如需停止服务，请手动 kill 进程")
        print("======================================\n")
        
        import time
        while True:
            # 每分钟检查一次进程是否还在运行
            time.sleep(60)
            if not check_process_running("sing-box"):
                print("警告: sing-box 进程已退出，容器即将退出")
                break


def update_singbox() -> None:
    """更新 Sing-box 内核"""
    print("=========更新Sing-box内核=========")

    # 停止服务
    stop_service("sb", "s")

    # 删除旧内核
    if os.path.exists(SB_CORE):
        os.remove(SB_CORE)

    # 下载新内核
    cpu = get_arch()
    url = (
        f"https://github.com/yonggekkk/argosbx/releases/download/argosbx/sing-box-{cpu}"
    )
    print("正在下载 Sing-box 内核...")
    download_binary(url, SB_CORE)

    if os.path.exists(SB_CORE):
        version = get_singbox_version()
        print(f"Sing-box 内核版本: {version}")

    restart_singbox()


def restart_singbox() -> None:
    """重启 Sing-box 服务"""
    print("=========重启Sing-box服务=========")

    if os.path.exists(SB_CONFIG):
        # 停止旧进程
        stop_service("sb", "s")

        # 重启服务
        install_systemd_service(
            "sb", f"{SB_CORE} run -c {SB_CONFIG}", "Sing-box service"
        )
        print("Sing-box 已重启")
    else:
        print("Sing-box 配置文件不存在，请先安装")


def stop_singbox() -> None:
    """停止 Sing-box 服务"""
    print("=========停止Sing-box服务=========")

    stop_service("sb", "s")

    print("Sing-box 已停止")


def singbox_status() -> None:
    """查看 Sing-box 运行状态"""
    print("=========Sing-box运行状态=========")

    if os.path.exists(SB_CORE):
        version = get_singbox_version()
        print(f"Sing-box 版本: {version}")
    else:
        print("Sing-box 内核未安装")

    if check_process_running("sing-box") or check_process_running("sb"):
        print("状态: 运行中")
    else:
        print("状态: 未运行")


def generate_nodes_text(uuid_val: str, server_ip: str, domain: str = "") -> str:
    lines = []
    hostname = get_hostname()
    sxname = read_file(os.path.join(AGSBX_DATA, "common", "name"))

    if domain:
        vl_link = f"vless://{uuid_val}@{domain}:443?path=/{uuid_val}-vl&security=tls&encryption=none&host={domain}&type=ws&sni={domain}#{sxname}vless-ws-tls-sb-{hostname}"
        lines.append(vl_link)

    port_ss_file = os.path.join(SB_DATA, "port_ss")
    if os.path.exists(port_ss_file):
        port_ss = read_file(port_ss_file)
        sskey = read_file(os.path.join(SB_DATA, "sskey"))
        ss_link = f"ss://2022-blake3-aes-128-gcm:{sskey}@{server_ip}:{port_ss}#{sxname}Shadowsocks-2022-{hostname}"
        lines.append(ss_link)

    port_vm_ws_file = os.path.join(SB_DATA, "port_vm_ws")
    if os.path.exists(port_vm_ws_file):
        port_vm_ws = read_file(port_vm_ws_file)
        vm_config = {
            "v": "2",
            "ps": f"{sxname}vm-sb-{hostname}",
            "add": server_ip,
            "port": port_vm_ws,
            "id": uuid_val,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": "www.bing.com",
            "path": f"/{uuid_val}-vm",
            "tls": "",
        }
        vm_link = f"vmess://{base64.b64encode(json.dumps(vm_config).encode()).decode()}"
        lines.append(vm_link)

    port_an_file = os.path.join(SB_DATA, "port_an")
    if os.path.exists(port_an_file):
        port_an = read_file(port_an_file)
        an_link = f"anytls://{uuid_val}@{server_ip}:{port_an}?insecure=1&allowInsecure=1#{sxname}anytls-{hostname}"
        lines.append(an_link)

    port_ar_file = os.path.join(SB_DATA, "port_ar")
    if os.path.exists(port_ar_file):
        port_ar = read_file(port_ar_file)
        ym_vl_re = read_file(os.path.join(AGSBX_DATA, "common", "ym_vl_re"))
        keys_dir = os.path.join(SB_DATA, "keys")
        public_key_s = read_file(os.path.join(keys_dir, "public_key"))
        short_id_s = read_file(os.path.join(keys_dir, "short_id"))
        ar_link = f"anytls://{uuid_val}@{server_ip}:{port_ar}?security=reality&sni={ym_vl_re}&fp=chrome&pbk={public_key_s}&sid={short_id_s}&type=tcp&headerType=none#{sxname}any-reality-{hostname}"
        lines.append(ar_link)

    port_hy2_file = os.path.join(SB_DATA, "port_hy2")
    if os.path.exists(port_hy2_file):
        port_hy2 = read_file(port_hy2_file)
        hy2_link = f"hysteria2://{uuid_val}@{server_ip}:{port_hy2}?security=tls&alpn=h3&insecure=1&sni=www.bing.com#{sxname}hy2-{hostname}"
        lines.append(hy2_link)

    port_tu_file = os.path.join(SB_DATA, "port_tu")
    if os.path.exists(port_tu_file):
        port_tu = read_file(port_tu_file)
        tuic5_link = f"tuic://{uuid_val}:{uuid_val}@{server_ip}:{port_tu}?congestion_control=bbr&udp_relay_mode=native&alpn=h3&sni=www.bing.com&allow_insecure=1&allowInsecure=1#{sxname}tuic-{hostname}"
        lines.append(tuic5_link)

    port_so_file = os.path.join(SB_DATA, "port_so")
    if os.path.exists(port_so_file):
        port_so = read_file(port_so_file)
        lines.append(f"Socks5 端口: {port_so}")
        lines.append(f"用户名: {uuid_val}")
        lines.append(f"密码: {uuid_val}")

    return "\n".join(lines)


class NodeRequestHandler(BaseHTTPRequestHandler):
    vless_url = ""

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            msg = "🟢恭喜！部署成功！欢迎使用甬哥YGkkk-ArgoSBX小钢炮脚本💣 【当前版本V25.11.20】\n\n查看节点信息路径：/你的uuid（已设uuid变量时）或者/subuuid（未设uuid变量时）"
            self.wfile.write(msg.encode("utf-8"))
        elif self.path.startswith("/"):
            nodes_file = os.path.join(AGSBX_DATA, "nodes.txt")
            if os.path.exists(nodes_file):
                with open(nodes_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if self.vless_url:
                    content = f"{self.vless_url}\n{content}"
                self.send_response(200)
                self.send_header("Content-type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-type", "text/plain; charset=utf-8")
                self.end_headers()
                msg = "❌Not Found：路径错误！！！\n\n查看节点信息路径：/你的uuid（已设uuid变量时）或者/subuuid（未设uuid变量时）"
                self.wfile.write(msg.encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            msg = "❌Not Found：路径错误！！！\n\n查看节点信息路径：/你的uuid（已设uuid变量时）或者/subuuid（未设uuid变量时）"
            self.wfile.write(msg.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def start_http_server(port: int, domain: str, uuid_val: str) -> None:
    vless_url = ""
    if domain:
        vless_url = f"vless://{uuid_val}@{domain}:443?path=/{uuid_val}-vl&security=tls&encryption=none&host={domain}&type=ws&sni={domain}#vless-ws-tls"

    NodeRequestHandler.vless_url = vless_url

    try:
        server = HTTPServer(("0.0.0.0", port), NodeRequestHandler)
        print(f"✅ HTTP 服务器已启动在端口 {port}")
        if vless_url:
            print(f"💣Vless-ws-tls节点分享:\n{vless_url}")
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
    except Exception as e:
        print(f"⚠️ HTTP 服务器启动失败: {e}")


def show_links() -> None:
    """显示节点配置"""
    print("=========Sing-box节点配置=========")

    # 获取服务器信息
    try:
        hostname_result = run_command(["hostname"])[1]
        hostname = hostname_result.strip() if hostname_result else "unknown"
    except Exception:
        hostname = "unknown"

    uuid_val = read_file(os.path.join(AGSBX_DATA, "common", "uuid"))
    server_ip = get_server_ip()

    if not uuid_val or not server_ip:
        print("错误: UUID 或服务器IP未配置")
        return

    sxname = read_file(os.path.join(AGSBX_DATA, "common", "name"))

    # Reality 密钥
    public_key_s = ""
    short_id_s = ""

    keys_dir = os.path.join(SB_DATA, "keys")
    if os.path.exists(os.path.join(keys_dir, "public_key")):
        public_key_s = read_file(os.path.join(keys_dir, "public_key"))
        short_id_s = read_file(os.path.join(keys_dir, "short_id"))

    sskey = read_file(os.path.join(SB_DATA, "sskey"))
    ym_vl_re = read_file(os.path.join(AGSBX_DATA, "common", "ym_vl_re"))

    print(f"服务器: {server_ip}")
    print(f"UUID: {uuid_val}")
    print("")

    # Shadowsocks-2022
    port_ss_file = os.path.join(SB_DATA, "port_ss")
    if os.path.exists(port_ss_file):
        port_ss = read_file(port_ss_file)
        print(f"【Shadowsocks-2022】端口: {port_ss}")
        ss_link = f"ss://2022-blake3-aes-128-gcm:{sskey}@{server_ip}:{port_ss}#{sxname}Shadowsocks-2022-{hostname}"
        print(ss_link)
        print("")

    # Vmess-ws
    port_vm_ws_file = os.path.join(SB_DATA, "port_vm_ws")
    if os.path.exists(port_vm_ws_file):
        port_vm_ws = read_file(port_vm_ws_file)
        print(f"【Vmess-ws】端口: {port_vm_ws}")
        vm_config = {
            "v": "2",
            "ps": f"{sxname}vm-sb-{hostname}",
            "add": server_ip,
            "port": port_vm_ws,
            "id": uuid_val,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": "www.bing.com",
            "path": f"/{uuid_val}-vm",
            "tls": "",
        }
        vm_link = f"vmess://{base64.b64encode(json.dumps(vm_config).encode()).decode()}"
        print(vm_link)
        print("")

    # AnyTLS
    port_an_file = os.path.join(SB_DATA, "port_an")
    if os.path.exists(port_an_file):
        port_an = read_file(port_an_file)
        print(f"【AnyTLS】端口: {port_an}")
        an_link = f"anytls://{uuid_val}@{server_ip}:{port_an}?insecure=1&allowInsecure=1#{sxname}anytls-{hostname}"
        print(an_link)
        print("")

    # Any-Reality
    port_ar_file = os.path.join(SB_DATA, "port_ar")
    if os.path.exists(port_ar_file):
        port_ar = read_file(port_ar_file)
        print(f"【Any-Reality】端口: {port_ar}")
        ar_link = f"anytls://{uuid_val}@{server_ip}:{port_ar}?security=reality&sni={ym_vl_re}&fp=chrome&pbk={public_key_s}&sid={short_id_s}&type=tcp&headerType=none#{sxname}any-reality-{hostname}"
        print(ar_link)
        print("")

    # Hysteria2
    port_hy2_file = os.path.join(SB_DATA, "port_hy2")
    if os.path.exists(port_hy2_file):
        port_hy2 = read_file(port_hy2_file)
        print(f"【Hysteria2】端口: {port_hy2}")
        hy2_link = f"hysteria2://{uuid_val}@{server_ip}:{port_hy2}?security=tls&alpn=h3&insecure=1&sni=www.bing.com#{sxname}hy2-{hostname}"
        print(hy2_link)
        print("")

    # Tuic
    port_tu_file = os.path.join(SB_DATA, "port_tu")
    if os.path.exists(port_tu_file):
        port_tu = read_file(port_tu_file)
        print(f"【Tuic】端口: {port_tu}")
        tuic5_link = f"tuic://{uuid_val}:{uuid_val}@{server_ip}:{port_tu}?congestion_control=bbr&udp_relay_mode=native&alpn=h3&sni=www.bing.com&allow_insecure=1&allowInsecure=1#{sxname}tuic-{hostname}"
        print(tuic5_link)
        print("")

    # Socks5
    port_so_file = os.path.join(SB_DATA, "port_so")
    if os.path.exists(port_so_file):
        port_so = read_file(port_so_file)
        print(f"【Socks5】端口: {port_so}")
        print(f"用户名: {uuid_val}")
        print(f"密码: {uuid_val}")
        print("")

    # Vless-ws-tls
    port_vl_ws_tls_file = os.path.join(SB_DATA, "port_vl_ws_tls")
    domain_file = os.path.join(SB_DATA, "domain")
    if os.path.exists(port_vl_ws_tls_file) and os.path.exists(domain_file):
        port_vl_ws_tls = read_file(port_vl_ws_tls_file)
        domain_val = read_file(domain_file)
        print(f"【Vless-ws-tls】端口: {port_vl_ws_tls}")
        print(f"服务器域名: {domain_val}")
        vl_config = {
            "v": "2",
            "ps": f"{sxname}vless-ws-tls-sb-{hostname}",
            "add": domain_val,
            "port": port_vl_ws_tls,
            "id": uuid_val,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": domain_val,
            "path": f"/{uuid_val}-vl",
            "tls": "tls",
            "sni": domain_val,
        }
        vl_link = f"vless://{uuid_val}@{domain_val}:{port_vl_ws_tls}?path=/{uuid_val}-vl&security=tls&encryption=none&host={domain_val}&type=ws&sni={domain_val}#{sxname}vless-ws-tls-sb-{hostname}"
        print(vl_link)
        print("")


def uninstall_singbox() -> None:
    """卸载 Sing-box"""
    print("=========卸载Sing-box=========")

    stop_service("sb", "s")

    # 删除文件
    if os.path.exists(SB_CORE):
        os.remove(SB_CORE)
    if os.path.exists(SB_CONFIG):
        os.remove(SB_CONFIG)

    # 删除数据目录
    if os.path.exists(SB_DATA):
        shutil.rmtree(SB_DATA)

    print("Sing-box 已卸载")


def parse_env_vars() -> Dict[str, str]:
    """
    解析环境变量中的协议参数

    Returns:
        dict: 包含协议参数的字典
    """
    result = {}

    # 从环境变量中获取参数
    env_vars = ["hypt", "tupt", "anpt", "arpt", "sspt", "vmpt", "sopt", "warp", "DOMAIN", "uuid"]

    for var in env_vars:
        value = os.environ.get(var, "")
        if value:
            result[var] = value
        # 也尝试大写
        value_upper = os.environ.get(var.upper(), "")
        if value_upper and var not in result:
            result[var] = value_upper

    return result


def main():
    """主函数"""
    if len(sys.argv) < 2:
        show_usage()
        return

    # 解析命令行参数
    command = sys.argv[1].lower()

    # 解析协议参数
    protocol_args = parse_env_vars()

    # 处理命令
    if command in ("install", "i"):
        install_singbox(
            hypt=protocol_args.get("hypt", ""),
            tupt=protocol_args.get("tupt", ""),
            anpt=protocol_args.get("anpt", ""),
            arpt=protocol_args.get("arpt", ""),
            sspt=protocol_args.get("sspt", ""),
            vmpt=protocol_args.get("vmpt", ""),
            sopt=protocol_args.get("sopt", ""),
            warp=protocol_args.get("warp", "sx"),
            DOMAIN=protocol_args.get("DOMAIN", ""),
            uuid=protocol_args.get("uuid", ""),
        )
    elif command in ("upsingbox", "ups", "u"):
        update_singbox()
    elif command in ("restart", "res", "r"):
        restart_singbox()
    elif command == "stop":
        stop_singbox()
    elif command in ("status", "stat", "s"):
        singbox_status()
    elif command in ("list", "l"):
        show_links()
    elif command in ("del", "uninstall", "d"):
        uninstall_singbox()
    elif command in ("help", "h", "--help", "-h"):
        show_usage()
    else:
        show_usage()


if __name__ == "__main__":
    main()
