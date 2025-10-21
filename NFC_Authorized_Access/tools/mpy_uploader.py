# Python env   : Python 3.12.0
# -*- coding: utf-8 -*-
# @Time    : 2025/9/20 下午5:53
# @Author  : 李清水
# @File    : mpy_uploader.py
# @Description : 使用mpremote将build/firmware_mpy/文件夹内容下载到MCU
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import sys
import subprocess
import argparse
from pathlib import Path

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================


class MPYDeployer:
    """
    MPY部署器类，Windows系统专用工具，用于通过mpremote将mpy文件及目录部署到MCU根目录。

    该类封装了与MCU设备的交互流程，包括列出可用串口设备、用户选择目标设备、部署单个mpy文件、
    部署整个目录结构以及查看MCU上的文件列表等核心功能。通过标准化的路径处理和命令调用，
    确保文件和目录能准确同步到MCU指定位置，并提供详细的部署结果反馈。

    Attributes:
        source_dir (Path): 源mpy文件及目录所在的绝对路径，默认为"..\\build\\firmware_mpy"。
        verbose (bool): 是否开启详细输出模式，True为开启，False为关闭。
        device_port (str | None): 目标MCU的串口端口号（如COM3），初始为None，需通过选择或指定获取。

    Methods:
        __init__(source_dir: str = "..\\build\\firmware_mpy", verbose: bool = False) -> None: 初始化部署器，验证源目录并输出基本信息。
        list_available_devices() -> list[dict[str, str]]: 列出系统中所有可用的串口设备，返回包含端口和描述的字典列表。
        select_device() -> str | None: 引导用户选择目标设备，支持手动选择或自动选择第一个设备。
        deploy_directories_to_root() -> bool: 将源目录下所有子目录部署到MCU根目录，返回是否全部部署成功。
        list_remote_files() -> bool: 列出MCU根目录下的所有文件及目录，返回是否执行成功。

    Notes:
        1. 依赖mpremote工具，需确保其已安装并添加到系统环境变量中。
        2. 部署目录时会使用递归复制（-r参数），确保子目录结构完整同步。
        3. 所有命令执行设有超时限制（文件30秒，目录60秒），避免无限阻塞。

    ==========================================

    MPY Deployer class, a Windows-specific tool for deploying mpy files and directories to MCU root directory via mpremote.

    This class encapsulates the interaction process with MCU devices, including listing available serial port devices,
    guiding users to select target devices, deploying individual mpy files, deploying entire directory structures,
    and viewing file lists on the MCU. Through standardized path processing and command calls, it ensures that files
    and directories are accurately synchronized to the specified location on the MCU, and provides detailed deployment
    result feedback.

    Attributes:
        source_dir (Path): Absolute path of the source mpy files and directories, default is "..\\build\\firmware_mpy".
        verbose (bool): Whether to enable verbose output mode, True for enabled, False for disabled.
        device_port (str | None): Serial port number of the target MCU (e.g., COM3), initially None, obtained via selection or specification.

    Methods:
        __init__(source_dir: str = "..\\build\\firmware_mpy", verbose: bool = False) -> None: Initialize the deployer, verify the source directory and output basic information.
        list_available_devices() -> list[dict[str, str]]: List all available serial port devices in the system, return a list of dicts containing port and description.
        select_device() -> str | None: Guide users to select the target device, supporting manual selection or automatic selection of the first device.
        deploy_directories_to_root() -> bool: Deploy all subdirectories in the source directory to MCU root directory, return whether all deployments are successful.
        list_remote_files() -> bool: List all files and directories in the MCU root directory, return whether the execution is successful.

    Notes:
        1. Depends on the mpremote tool, which must be installed and added to the system environment variables.
        2. Recursive copy (-r parameter) is used when deploying directories to ensure complete synchronization of subdirectory structures.
        3. All command executions have timeout limits (30s for files, 60s for directories) to avoid infinite blocking.
    """

    def __init__(
        self, source_dir: str = "../build/firmware_mpy", verbose: bool = False
    ):
        """
        初始化MPY部署器实例，完成源目录路径规范化及有效性校验。

        Args:
            source_dir: 源mpy文件及目录的路径字符串，默认为"..\\build\\firmware_mpy"。
            verbose: 是否开启详细输出模式，True显示详细日志，False仅显示关键信息。

        Raises:
            FileNotFoundError: 若指定的源目录不存在。

        ==========================================

        Initialize the MPY deployer instance, complete source directory path normalization and validity verification.

        Args:
            source_dir: Path string of the source mpy files and directories, default is "..\\build\\firmware_mpy".
            verbose: Whether to enable verbose output mode, True for detailed logs, False for only key information.

        Raises:
            FileNotFoundError: If the specified source directory does not exist.
        """
        self.source_dir = Path(source_dir).resolve()
        self.verbose = verbose
        self.device_port: str | None = None

        # 检查源目录是否存在
        if not self.source_dir.exists():
            raise FileNotFoundError(f"源目录不存在: {self.source_dir}")

        # 输出源目录的绝对路径
        print(f"初始化部署器，源目录绝对路径: {self.source_dir}")

    def list_available_devices(self) -> list[dict[str, str]]:
        """
        列出系统中所有可用的串口设备，返回设备信息字典列表。

        通过调用mpremote的"connect list"命令获取设备列表，解析输出结果提取端口号（如COM3）
        和设备描述信息，过滤无效设备条目后返回结构化数据。若命令执行失败或超时，返回空列表。

        Returns:
            list[dict[str, str]]: 可用设备列表，每个元素为包含"port"（端口号）和"description"（设备描述）的字典。

        ==========================================

        List all available serial port devices in the system, return a list of device information dicts.

        Obtain the device list by calling the "connect list" command of mpremote, parse the output to extract
        the port number (e.g., COM3) and device description, filter invalid device entries, and return structured data.
        Return an empty list if the command execution fails or times out.

        Returns:
            list[dict[str, str]]: List of available devices, each element is a dict containing "port" (port number) and "description" (device description).
        """
        try:
            result = subprocess.run(
                ["mpremote", "connect", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                print("无法列出设备，请确保mpremote已安装")
                return []

            devices: list[dict[str, str]] = []
            lines = result.stdout.strip().split("\n")

            # 解析设备列表
            for line in lines:
                if line.strip() and ("COM" in line or "/dev/" in line):
                    parts = line.split()
                    if parts:  # 确保有内容
                        # 第一个部分通常是端口名
                        port = parts[0]

                        # 检查是否是COM端口或USB设备
                        if port.startswith("COM") or port.startswith("/dev/"):
                            # 其余部分作为描述
                            description = (
                                " ".join(parts[1:])
                                if len(parts) > 1
                                else "Unknown device"
                            )
                            devices.append({"port": port, "description": description})

            return devices

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"错误: {e}")
            return []

    def select_device(self) -> str | None:
        """
        引导用户选择目标MCU设备，支持手动选择或自动选择模式。

        先调用list_available_devices()获取可用设备，若无可选设备返回None。
        显示设备列表供用户选择，支持直接回车自动选择第一个设备，输入无效值时默认自动选择。

        Returns:
            str | None: 选中的设备端口号或"auto"（自动选择），无设备时返回None。

        ==========================================

        Guide users to select the target MCU device, supporting manual selection or automatic selection mode.

        First call list_available_devices() to get available devices, return None if no devices are available.
        Display the device list for user selection, support pressing Enter to automatically select the first device,
        and default to automatic selection when invalid input is entered.

        Returns:
            str | None: Selected device port number or "auto" (automatic selection), return None when no devices are available.
        """
        devices = self.list_available_devices()

        if not devices:
            print("未找到可用设备，请确保MCU已连接")
            return None

        print("可用设备:")
        for i, device in enumerate(devices):
            print(f"{i + 1}. {device['port']} - {device['description']}")

        print(f"{len(devices) + 1}. 自动选择第一个可用设备")

        try:
            choice = input("请选择设备 (默认自动选择): ")
            if not choice:
                return "auto"

            choice = int(choice)
            if 1 <= choice <= len(devices):
                return devices[choice - 1]["port"]
            elif choice == len(devices) + 1:
                return "auto"
            else:
                print("无效选择，使用自动选择")
                return "auto"
        except ValueError:
            print("无效输入，使用自动选择")
            return "auto"

    def deploy_directories_to_root(self):
        """
        将源目录下所有子目录部署到MCU根目录，返回部署结果状态。

        若未指定设备端口，先调用select_device()获取。调用mpremote的fs cp -r命令递归部署目录.

        ==========================================

        Deploy all subdirectories in the source directory to the MCU root directory, return the deployment result status.

        If no device port is specified, call select_device() first. call the fs cp -r command of mpremote to deploy directories recursively.

        """
        if not self.device_port:
            self.device_port = self.select_device()
            if not self.device_port:
                return False

        print(f"开始部署目录到设备根目录: {self.device_port}")

        try:
            # 遍历目录下的所有文件和文件夹
            for item in self.source_dir.iterdir():
                print(f"部署: {item.name}")
                cmd = [
                    "mpremote",
                    "connect",
                    self.device_port,
                    "fs",
                    "cp",
                    "-r",
                    str(item),
                    ":",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    print(f"✗ 复制 {item.name} 失败: {result.stderr}")
                else:
                    print(f"✓ 已复制 {item.name}")

            print("✓ 目录部署完成")
            return True

        except subprocess.TimeoutExpired:
            print("✗ 部署目录超时")
            return False

    def list_remote_files(self) -> bool:
        """
        列出MCU根目录下的所有文件及目录，返回命令执行状态。

        若未指定设备端口，先调用select_device()获取。调用mpremote的fs ls -r命令
        递归列出MCU根目录内容，成功则打印结果，失败则输出错误信息，返回执行是否成功。

        Returns:
            bool: True表示命令执行成功并获取文件列表，False表示执行失败。

        ==========================================

        List all files and directories in the MCU root directory, return the command execution status.

        If no device port is specified, call select_device() first. Call the fs ls -r command of mpremote
        to recursively list the contents of the MCU root directory, print the result if successful, output
        an error message if failed, and return whether the execution is successful.

        Returns:
            bool: True means the command is executed successfully and the file list is obtained, False means execution failed.
        """
        if not self.device_port:
            self.device_port = self.select_device()
            if not self.device_port:
                return False

        try:
            cmd = ["mpremote", "connect", self.device_port, "fs", "ls", "-r", ":"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                print("MCU上的文件:")
                print(result.stdout)
                return True
            else:
                print(f"无法列出文件: {result.stderr}")
                return False

        except Exception as e:
            print(f"错误: {e}")
            return False


# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="使用mpremote工具部署mpy文件到MCU根目录",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-s",
        "--source",
        help="源mpy文件目录，默认为./build/firmware_mpy",
        default="./build/firmware_mpy",
    )

    parser.add_argument("-d", "--device", help="指定设备端口（如COM3），默认为自动选择")

    parser.add_argument("-v", "--verbose", help="显示详细输出", action="store_true")

    parser.add_argument("-a", "--all", help="部署所有文件和目录到MCU根目录", action="store_true")

    parser.add_argument("-l", "--list", help="只列出MCU上的文件，不部署", action="store_true")

    args = parser.parse_args()

    try:
        deployer = MPYDeployer(source_dir=args.source, verbose=args.verbose)

        if args.device:
            deployer.device_port = args.device
        if args.list:
            deployer.list_remote_files()
        else:
            print("开始部署：部署目录 -> 根目录 ...")
            deployer.deploy_directories_to_root()

    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
