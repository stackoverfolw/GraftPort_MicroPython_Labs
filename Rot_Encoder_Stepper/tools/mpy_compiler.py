# Python env   : Python 3.12.0
# -*- coding: utf-8 -*-
# @Time    : 2025/9/20 下午5:23
# @Author  : 李清水
# @File    : mpy_compiler.py
# @Description : 专注于按依赖顺序将Python文件编译为mpy文件的工具（仅编译功能）
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from collections import defaultdict, deque
from dependency_analyzer import DependencyAnalyzer

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================


class MPYCompiler:
    """
    MPY编译器类，专注于按依赖顺序将Python文件编译为mpy文件的核心工具。

    该类封装了完整的MPY编译工作流，包括源目录验证、Python文件依赖分析、基于拓扑排序的编译顺序确定、
    调用mpy-cross工具编译单个文件，以及输出目录的结构管理。通过严格遵循依赖顺序编译，可以确保被导入的模块
    先于导入它的模块完成编译，避免因依赖问题导致的编译错误。

    Attributes:
        source_dir (Path): 源Python文件目录的绝对路径，默认为"../firmware"。
        output_dir (Path): 编译后mpy文件输出目录的绝对路径，默认为"../build/firmware_mpy"。
        mpy_cross_opts (list[str]): 传递给mpy-cross工具的编译选项列表，如架构、兼容版本等。
        verbose (bool): 是否开启详细日志输出模式，True为开启，False为关闭。
        dependency_analyzer (DependencyAnalyzer | None): 依赖分析器实例，用于扫描和解析文件依赖，初始为None。
        dependencies (dict[str, set[str]]): 存储文件依赖关系的字典，键为文件名（含路径），值为其依赖的文件名集合。
        compile_order (list[str]): 按依赖顺序排序的待编译文件列表，先编译被依赖文件。

    Methods:
        __init__(source_dir: str = "../firmware", output_dir: str = "../build/firmware_mpy", mpy_cross_opts: list[str] | None = None, verbose: bool = False) -> None: 初始化MPY编译器实例，验证源目录并准备输出目录。
        _check_required_files() -> None: 内部方法，检查源目录是否包含boot.py、main.py等必要文件。
        analyze_dependencies() -> None: 分析源目录中Python文件的内部依赖关系，生成依赖数据。
        _extract_dependencies() -> None: 内部方法，从dependency_analyzer中提取并格式化依赖关系到dependencies属性。
        determine_compile_order() -> None: 基于依赖关系进行拓扑排序，确定最终的文件编译顺序，处理循环依赖。
        compile_files() -> None: 按compile_order编译所有文件，清空输出目录、复制目录结构并统计编译结果。
        _copy_directory_structure() -> None: 内部方法，复制源目录的目录结构到输出目录（不复制文件）。
        _compile_single_file(file_path: str) -> None: 内部方法，调用mpy-cross工具编译单个Python文件为mpy文件。
        run() -> None: 执行完整编译流程：依赖分析→确定顺序→编译文件，捕获并处理流程中的异常。

    Notes:
        1. 依赖分析功能依赖外部的DependencyAnalyzer类，需确保该模块可正常导入。
        2. 初始化时会自动创建输出目录（若不存在），编译前会清空输出目录中的现有内容。
        3. 若检测到循环依赖，会将未通过拓扑排序的文件追加到编译顺序末尾，并输出警告（verbose模式下）。
        4. 编译结果会输出成功/失败数量及失败文件详情，最终显示输出目录路径。

    ==========================================

    MPY Compiler class, a core tool dedicated to compiling Python files into mpy files in dependency order.

    This class encapsulates the complete MPY compilation workflow, including source directory verification,
    Python file dependency analysis, determination of compilation order based on topological sorting,
    invoking the mpy-cross tool to compile individual files, and management of the output directory structure.
    By strictly following the dependency order for compilation, it ensures that imported modules are compiled
    before the modules that import them, avoiding compilation errors caused by dependency issues.

    Attributes:
        source_dir (Path): Absolute path of the source Python file directory, default is "../firmware".
        output_dir (Path): Absolute path of the output directory for compiled mpy files, default is "../build/firmware_mpy".
        mpy_cross_opts (list[str]): List of compilation options passed to the mpy-cross tool, such as architecture and compatibility version.
        verbose (bool): Whether to enable verbose log output mode, True for enabled, False for disabled.
        dependency_analyzer (DependencyAnalyzer | None): Instance of the dependency analyzer, used to scan and parse file dependencies, initially None.
        dependencies (dict[str, set[str]]): Dictionary storing file dependency relationships, with keys as filenames (including paths) and values as sets of dependent filenames.
        compile_order (list[str]): List of files to be compiled sorted by dependency order, with dependent files compiled first.

    Methods:
        __init__(source_dir: str = "../firmware", output_dir: str = "../build/firmware_mpy", mpy_cross_opts: list[str] | None = None, verbose: bool = False) -> None: Initialize the MPY compiler instance, verify the source directory and prepare the output directory.
        _check_required_files() -> None: Internal method to check if the source directory contains necessary files like boot.py and main.py.
        analyze_dependencies() -> None: Analyze internal dependencies of Python files in the source directory and generate dependency data.
        _extract_dependencies() -> None: Internal method to extract and format dependency relationships from dependency_analyzer into the dependencies attribute.
        determine_compile_order() -> None: Perform topological sorting based on dependencies to determine the final file compilation order and handle circular dependencies.
        compile_files() -> None: Compile all files in compile_order, clear the output directory, copy the directory structure, and count compilation results.
        _copy_directory_structure() -> None: Internal method to copy the directory structure of the source directory to the output directory (without copying files).
        _compile_single_file(file_path: str) -> None: Internal method to invoke the mpy-cross tool to compile a single Python file into an mpy file.
        run() -> None: Execute the complete compilation process: dependency analysis → order determination → file compilation, catch and handle exceptions in the process.

    Notes:
        1. The dependency analysis function relies on the external DependencyAnalyzer class; ensure this module can be imported normally.
        2. The output directory is automatically created during initialization (if it does not exist), and existing content in the output directory is cleared before compilation.
        3. If circular dependencies are detected, files that fail topological sorting will be appended to the end of the compilation order, and a warning will be output (in verbose mode).
        4. The compilation results will output the number of successful/failed compilations and details of failed files, and finally display the output directory path.
    """

    def __init__(
        self,
        source_dir: str = "../firmware",
        output_dir: str = "../build/firmware_mpy",
        mpy_cross_opts: list[str] | None = None,
        verbose: bool = False,
    ):
        """
        初始化MPY编译器实例，完成路径规范化、输出目录创建及必要校验。

        Args:
            source_dir: 源Python文件目录的路径字符串，默认为"../firmware"。
            output_dir: 编译后mpy文件输出目录的路径字符串，默认为"../build/firmware_mpy"。
            mpy_cross_opts: 传递给mpy-cross工具的编译选项列表，为None时初始化为空列表。
            verbose: 是否开启详细日志输出，True显示详细信息，False仅显示关键信息。

        Raises:
            FileNotFoundError: 若指定的源目录不存在，或源目录缺少必要文件。

        ==========================================

        Initialize the MPY compiler instance, complete path normalization, output directory creation, and necessary verification.

        Args:
            source_dir: Path string of the source Python file directory, default is "../firmware".
            output_dir: Path string of the output directory for compiled mpy files, default is "../build/firmware_mpy".
            mpy_cross_opts: List of compilation options passed to the mpy-cross tool, initialized as an empty list if None.
            verbose: Whether to enable verbose log output, True for detailed information, False for only key information.

        Raises:
            FileNotFoundError: If the specified source directory does not exist, or the source directory lacks necessary files.
        """
        # 规范化路径
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化编译选项
        self.mpy_cross_opts = mpy_cross_opts if mpy_cross_opts else []
        self.verbose = verbose

        # 存储依赖分析结果
        self.dependency_analyzer = None
        self.dependencies = {}  # {文件名: 依赖文件列表}
        self.compile_order = []  # 编译顺序列表

        # 检查源目录是否存在
        if not self.source_dir.exists():
            raise FileNotFoundError(f"源目录不存在: {self.source_dir}")

        # 检查必要的文件是否存在
        self._check_required_files()

    def _check_required_files(self) -> None:
        """
        内部方法：检查源目录中是否存在固件运行必需的核心文件。

        校验的必需文件包括boot.py、main.py、conf.py、board.py，这些文件是MicroPython固件
        启动和运行的基础组件。若缺失任何一个文件，将抛出FileNotFoundError异常。

        Raises:
            FileNotFoundError: 若源目录中存在缺失的必需文件，异常信息包含缺失文件名及源目录路径。

        ==========================================

        Internal method: Check if the source directory contains core files necessary for firmware operation.

        The required files to verify include boot.py, main.py, conf.py, and board.py, which are basic components
        for the startup and operation of MicroPython firmware. If any file is missing, a FileNotFoundError exception is raised.

        Raises:
            FileNotFoundError: If there are missing required files in the source directory, the exception message includes the missing filenames and source directory path.
        """
        required_files = ["boot.py", "main.py", "conf.py", "board.py"]

        missing_files = []
        for file in required_files:
            file_path = self.source_dir / file
            if not file_path.exists():
                missing_files.append(file)

        if missing_files:
            raise FileNotFoundError(
                f"固件目录缺少必要文件: {', '.join(missing_files)}\n"
                f"请检查源目录: {self.source_dir}"
            )

    def analyze_dependencies(self) -> None:
        """
        分析源目录中所有Python文件的内部依赖关系，生成依赖数据。

        该方法通过初始化DependencyAnalyzer实例，执行完整的依赖分析流程（扫描文件、构建模块映射、
        解析导入语句、添加强制依赖、构建反向链接），并调用_extract_dependencies()方法提取
        格式化的依赖关系到dependencies属性中。verbose模式下会输出分析开始和完成的日志。

        ==========================================

        Analyze internal dependencies of all Python files in the source directory and generate dependency data.

        This method initializes a DependencyAnalyzer instance, executes the complete dependency analysis process (scanning files,
        building module maps, parsing import statements, adding forced dependencies, building reverse links), and calls the
        _extract_dependencies() method to extract formatted dependency relationships into the dependencies attribute.
        Logs of the start and completion of analysis are output in verbose mode.
        """
        if self.verbose:
            print(f"开始分析依赖关系，源目录: {self.source_dir}")

        # 使用依赖分析器获取依赖关系
        self.dependency_analyzer = DependencyAnalyzer(
            root=str(self.source_dir),
            out_md=str(self.output_dir.parent / "dependencies.md"),
            verbose=self.verbose,
        )

        # 运行完整的依赖分析流程
        self.dependency_analyzer.scan_files()
        self.dependency_analyzer.build_module_map()
        self.dependency_analyzer.parse_all_files()
        self.dependency_analyzer._add_main_forced_deps()
        self.dependency_analyzer.link_reverse()

        # 提取依赖关系
        self._extract_dependencies()

        if self.verbose:
            print(f"依赖分析完成，共分析 {len(self.dependencies)} 个文件")

    def _extract_dependencies(self) -> None:
        """
        内部方法：从DependencyAnalyzer实例中提取并格式化文件依赖关系。

        遍历dependency_analyzer的nodes属性（存储模块依赖节点），将每个模块ID转换为对应的Python
        文件名（替换路径分隔符并添加.py后缀），并收集该文件的内部依赖模块对应的文件名，存储到
        dependencies属性中（键为文件名，值为依赖文件名的集合）。

        ==========================================

        Internal method: Extract and format file dependency relationships from the DependencyAnalyzer instance.

        Traverse the nodes attribute of dependency_analyzer (storing module dependency nodes), convert each module ID to the
        corresponding Python filename (replace path separators and add .py suffix), collect filenames corresponding to the
        internal dependency modules of the file, and store them in the dependencies attribute (keys are filenames, values are sets of dependent filenames).
        """
        self.dependencies = {}

        # 遍历所有节点，提取依赖关系
        for module_id, node in self.dependency_analyzer.nodes.items():
            # 将module_id转换为文件路径（加上.py后缀）
            file_path = module_id.replace("/", os.sep) + ".py"

            # 获取该文件的内部依赖
            internal_deps = set()
            for dep_module_id in node.imports_internal:
                # 将依赖的module_id转换为文件路径
                dep_file_path = dep_module_id.replace("/", os.sep) + ".py"
                internal_deps.add(dep_file_path)

            self.dependencies[file_path] = internal_deps

    def determine_compile_order(self) -> None:
        """
        基于依赖关系进行拓扑排序，确定Python文件的编译顺序，优先编译被依赖文件。

        首先构建依赖图（邻接表）和入度表，然后通过拓扑排序算法处理入度为0的节点（无依赖文件），
        逐步生成编译顺序。若拓扑排序结果不完整（存在循环依赖），则将未处理的文件追加到编译顺序末尾，
        verbose模式下会输出循环依赖警告。若未先执行analyze_dependencies()，将抛出RuntimeError。

        Raises:
            RuntimeError: 若未先调用analyze_dependencies()方法生成依赖数据。

        ==========================================

        Perform topological sorting based on dependencies to determine the compilation order of Python files, with dependent files compiled first.

        First, build a dependency graph (adjacency list) and an in-degree table, then process nodes with in-degree 0 (files with no dependencies)
        through the topological sorting algorithm to gradually generate the compilation order. If the topological sorting result is incomplete
        (circular dependencies exist), the unprocessed files are appended to the end of the compilation order, and a circular dependency warning
        is output in verbose mode. A RuntimeError is raised if analyze_dependencies() is not executed first.

        Raises:
            RuntimeError: If the analyze_dependencies() method is not called first to generate dependency data.
        """
        if not self.dependencies:
            raise RuntimeError("请先调用analyze_dependencies()分析依赖关系")

        # 构建依赖图（邻接表表示）
        graph = defaultdict(list)
        in_degree = defaultdict(int)

        # 构建图和入度表
        for file, deps in self.dependencies.items():
            for dep in deps:
                if dep in self.dependencies:  # 只考虑项目内的依赖
                    graph[dep].append(file)
                    in_degree[file] += 1

        # 初始化入度为0的文件（没有依赖其他文件）
        queue = deque(
            [file for file in self.dependencies if in_degree.get(file, 0) == 0]
        )
        self.compile_order = []

        # 拓扑排序
        while queue:
            file = queue.popleft()
            self.compile_order.append(file)

            # 处理依赖于当前文件的其他文件
            for dependent in graph[file]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # 检查是否存在循环依赖
        if len(self.compile_order) != len(self.dependencies):
            unprocessed = [
                file for file in self.dependencies if file not in self.compile_order
            ]
            if self.verbose:
                print(f"警告: 检测到循环依赖，以下文件将按默认顺序编译: {unprocessed}")
            self.compile_order.extend(unprocessed)

        if self.verbose:
            print(f"已确定编译顺序，共 {len(self.compile_order)} 个文件")

    def compile_files(self) -> None:
        """
        按照determine_compile_order()确定的顺序，编译所有Python文件为mpy文件。

        执行流程包括：清空输出目录现有内容、复制源目录结构到输出目录、按顺序调用_compile_single_file()
        编译每个文件，并统计编译成功/失败的数量及失败文件详情。最后输出编译结果摘要（成功数、失败数、总计）
        及输出目录路径。若未先执行determine_compile_order()，将抛出RuntimeError。

        Raises:
            RuntimeError: 若未先调用determine_compile_order()方法确定编译顺序。

        ==========================================

        Compile all Python files into mpy files in the order determined by determine_compile_order().

        The execution process includes: clearing existing content in the output directory, copying the source directory structure to the output directory,
        calling _compile_single_file() to compile each file in order, and counting the number of successful/failed compilations and details of failed files.
        Finally, output a summary of compilation results (number of successes, failures, total) and the output directory path. A RuntimeError is raised if
        determine_compile_order() is not executed first.

        Raises:
            RuntimeError: If the determine_compile_order() method is not called first to determine the compilation order.
        """
        if not self.compile_order:
            raise RuntimeError("请先调用determine_compile_order()确定编译顺序")

        # 先清空输出目录，但保留目录结构
        if self.output_dir.exists():
            for item in self.output_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        # 复制目录结构
        self._copy_directory_structure()

        # 按顺序编译文件
        total_files = len(self.compile_order)
        success_count = 0
        fail_count = 0
        failed_files = []

        for i, file_path in enumerate(self.compile_order, 1):
            try:
                if self.verbose:
                    print(f"正在编译 ({i}/{total_files}): {file_path}")
                else:
                    print(f"编译中... ({i}/{total_files})", end="\r")

                self._compile_single_file(file_path)
                success_count += 1
            except Exception as e:
                fail_count += 1
                failed_files.append((file_path, str(e)))
                if self.verbose:
                    print(f"编译失败 {file_path}: {str(e)}")
        # 复制不能编译的文件
        shutil.copy(f'{self.source_dir}/main.py', f'{self.output_dir}/main.py')
        shutil.copy(f'{self.source_dir}/boot.py', f'{self.output_dir}/boot.py')
        Path(f'{self.output_dir}/main.mpy').unlink(missing_ok=True)
        Path(f'{self.output_dir}/boot.mpy').unlink(missing_ok=True)
        # 输出编译结果摘要
        print("\n" + "=" * 50)
        print(f"编译完成: 成功 {success_count}, 失败 {fail_count}, 总计 {total_files}")

        if failed_files:
            print("\n编译失败的文件:")
            for file, error in failed_files:
                print(f"  {file}: {error}")

        print("\n输出目录: " + str(self.output_dir))

    def _copy_directory_structure(self) -> None:
        """
        内部方法：复制源目录的完整目录结构到输出目录，不复制文件本身。

        通过os.walk()遍历源目录的所有子目录，计算每个子目录相对于源目录的相对路径，
        并在输出目录中创建对应的子目录。verbose模式下会输出每个创建的目录路径。

        ==========================================

        Internal method: Copy the complete directory structure of the source directory to the output directory without copying the files themselves.

        Traverse all subdirectories of the source directory via os.walk(), calculate the relative path of each subdirectory relative to the source directory,
        and create the corresponding subdirectory in the output directory. The path of each created directory is output in verbose mode.
        """
        for root, dirs, _ in os.walk(self.source_dir):
            rel_path = os.path.relpath(root, self.source_dir)
            target_dir = self.output_dir / rel_path
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                if self.verbose:
                    print(f"创建目录: {target_dir}")

    def _compile_single_file(self, file_path: str) -> None:
        """
        内部方法：调用mpy-cross工具编译单个Python文件为mpy文件。

        首先验证源文件是否存在，然后构建输出mpy文件的路径（替换.py为.mpy，保持相对路径结构），
        确保输出文件所在目录存在。接着构建mpy-cross的命令行（包含源文件、输出文件及编译选项），
        通过subprocess.run()执行命令，若返回码非0则抛出RuntimeError。verbose模式下输出编译成功日志。

        Args:
            file_path: 待编译的Python文件路径（相对于源目录的路径字符串）。

        Raises:
            FileNotFoundError: 若待编译的源文件不存在。
            RuntimeError: 若mpy-cross命令执行失败（返回码非0）或执行过程中出现异常。

        ==========================================

        Internal method: Invoke the mpy-cross tool to compile a single Python file into an mpy file.

        First, verify if the source file exists, then build the path of the output mpy file (replace .py with .mpy, maintain the relative path structure),
        and ensure the directory where the output file is located exists. Next, build the command line for mpy-cross (including source file, output file, and
        compilation options), execute the command via subprocess.run(), and raise a RuntimeError if the return code is non-zero. A log of successful compilation
        is output in verbose mode.

        Args:
            file_path: Path string of the Python file to be compiled (relative to the source directory).

        Raises:
            FileNotFoundError: If the source file to be compiled does not exist.
            RuntimeError: If the mpy-cross command execution fails (non-zero return code) or an exception occurs during execution.
        """
        source_file = self.source_dir / file_path
        if not source_file.exists():
            raise FileNotFoundError(f"源文件不存在: {source_file}")

        # 构建输出文件路径
        rel_path = os.path.relpath(source_file, self.source_dir)
        output_file = self.output_dir / rel_path.replace(".py", ".mpy")

        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 构建mpy-cross命令
        cmd = ["python", "-m", "mpy_cross", str(source_file), "-o", str(output_file)]

        # 添加额外编译选项
        cmd.extend(self.mpy_cross_opts)

        # 执行编译命令
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"编译错误: {result.stderr}")

            if self.verbose:
                print(f"编译成功: {output_file}")

        except Exception as e:
            raise RuntimeError(f"编译失败: {str(e)}") from e

    def run(self) -> None:
        """
        执行完整的MPY编译流程，串联依赖分析、顺序确定和文件编译环节。

        按顺序调用analyze_dependencies()、determine_compile_order()、compile_files()方法，
        捕获流程中可能抛出的所有异常，将错误信息输出到标准错误流，并以状态码1退出程序。

        ==========================================

        Execute the complete MPY compilation process, linking dependency analysis, order determination, and file compilation.

        Call the analyze_dependencies(), determine_compile_order(), and compile_files() methods in sequence, catch all exceptions that may be thrown
        during the process, output error information to the standard error stream, and exit the program with status code 1.
        """
        try:
            self.analyze_dependencies()
            self.determine_compile_order()
            self.compile_files()
        except Exception as e:
            print(f"错误: {str(e)}", file=sys.stderr)
            sys.exit(1)


# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    """命令行入口函数"""
    parser = argparse.ArgumentParser(
        description="MPY编译器 - 仅用于按依赖顺序将Python文件编译为mpy文件",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-s",
        "--source",
        help=f"源Python文件目录，默认为../firmware",
        default="../firmware",
    )

    parser.add_argument(
        "-o",
        "--output",
        help=f"编译后的mpy文件输出目录，默认为../build/firmware_mpy",
        default="../build/firmware_mpy",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        help="显示详细编译信息，-v显示基本信息，-vv显示详细信息",
        action="count",
        default=0,
    )

    parser.add_argument(
        "--compat", help="指定MicroPython兼容版本，如1.19", metavar="VERSION"
    )

    parser.add_argument(
        "--bytecode", help="指定字节码版本", type=int, metavar="VERSION"
    )

    parser.add_argument("-O", help="字节码优化级别，如-O2", metavar="LEVEL")

    parser.add_argument(
        "--arch", help="指定目标架构，如armv7m, xtensa等", metavar="ARCH"
    )

    args = parser.parse_args()

    # 构建mpy-cross编译选项
    mpy_cross_opts = []
    if args.compat:
        mpy_cross_opts.extend(["--compat", args.compat])
    if args.bytecode:
        mpy_cross_opts.extend(["--bytecode", str(args.bytecode)])
    if args.O:
        mpy_cross_opts.append(f"-{args.O}")
    if args.arch:
        mpy_cross_opts.extend(["-march", args.arch])

    # 初始化并运行编译器
    compiler = MPYCompiler(
        source_dir=args.source,
        output_dir=args.output,
        mpy_cross_opts=mpy_cross_opts,
        verbose=bool(args.verbose),
    )

    compiler.run()
