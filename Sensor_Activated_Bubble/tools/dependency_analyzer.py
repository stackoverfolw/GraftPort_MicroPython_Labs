# Python env   : Python 3.12.0
# -*- coding: utf-8 -*-
# @Time    : 2025/9/20 上午10:31
# @Author  : 李清水
# @File    : dependency_analyzer.py
# @Description : 面向对象的 Python 文件依赖分析器。
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

import ast
import os
import sys
import argparse
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple, Callable
import re
import html
import math

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================


class FileNode:
    """
    表示单个Python文件的节点类，用于存储文件元信息及其依赖关系。

    该类封装了Python文件的标识信息、路径信息以及依赖关系数据，
    包括内部模块依赖、外部模块依赖和反向依赖（被哪些模块依赖），
    并提供了将这些信息转换为Markdown表格行的方法。

    Attributes:
        module_id (str): 模块唯一标识符（相对路径，不含.py后缀，使用/分隔）。
        path (str): 文件的绝对路径。
        dotted_name (Optional[str]): 模块的点分名称（如pkg.sub.module），可能为None。
        imports_internal (Set[str]): 依赖的内部模块集合（存储module_id）。
        imports_external (Set[str]): 依赖的外部模块集合（存储模块名）。
        imported_by (Set[str]): 反向依赖集合（存储依赖当前模块的module_id）。

    Methods:
        __init__(module_id: str, path: str, dotted_name: Optional[str]) -> None: 初始化FileNode实例。
        to_md_row() -> str: 将节点信息转换为Markdown表格行字符串。

    Notes:
        imports_internal、imports_external和imported_by均使用集合类型以避免重复。
        当dotted_name为None时，表示无法解析为有效的点分名称。
        集合为空时，在Markdown表格中会显示为"-"。

    ==========================================

    Class representing a single Python file node, storing file metadata and dependency information.

    This class encapsulates identification information, path information, and dependency data of Python files,
    including internal module dependencies, external module dependencies, and reverse dependencies (which modules depend on it),
    and provides a method to convert this information into a Markdown table row.

    Attributes:
        module_id (str): Unique module identifier (relative path without .py suffix, using / as separator).
        path (str): Absolute path of the file.
        dotted_name (Optional[str]): Dotted name of the module (e.g., pkg.sub.module), may be None.
        imports_internal (Set[str]): Set of internal dependencies (storing module_ids).
        imports_external (Set[str]): Set of external dependencies (storing module names).
        imported_by (Set[str]): Set of reverse dependencies (storing module_ids that depend on current module).

    Methods:
        __init__(module_id: str, path: str, dotted_name: Optional[str]) -> None: Initialize FileNode instance.
        to_md_row() -> str: Convert node information to a Markdown table row string.

    Notes:
        imports_internal, imports_external, and imported_by use set type to avoid duplicates.
        When dotted_name is None, it indicates that it cannot be resolved to a valid dotted name.
        Empty sets will be displayed as "-" in the Markdown table.
    """

    def __init__(self, module_id: str, path: str, dotted_name: Optional[str]) -> None:
        """
        初始化FileNode实例，设置模块标识、路径和点分名称，并初始化依赖集合。

        Args:
            module_id (str): 模块唯一标识符，采用相对路径格式（不含.py后缀，用/分隔）。
            path (str): 文件的绝对路径，用于定位文件和获取文件大小。
            dotted_name (Optional[str]): 模块的点分名称，若无法解析则为None。

        ==========================================

        Initialize FileNode instance, set module identifier, path and dotted name, and initialize dependency sets.

        Args:
            module_id (str): Unique module identifier in relative path format (without .py suffix, using / as separator).
            path (str): Absolute path of the file, used for locating the file and getting file size.
            dotted_name (Optional[str]): Dotted name of the module, None if cannot be resolved.
        """
        self.module_id: str = module_id
        self.path: str = path
        self.dotted_name: Optional[str] = dotted_name
        self.imports_internal: Set[str] = set()  # 内部模块依赖 (Internal module dependencies)
        self.imports_external: Set[str] = set()  # 外部模块依赖 (External module dependencies)
        self.imported_by: Set[str] = set()  # 被哪些模块依赖 (Modules that depend on this module)

    def to_md_row(self) -> str:
        """
        将当前节点的信息转换为Markdown表格的一行，包含模块标识、点分名称、大小及依赖信息。

        转换逻辑：
        - 文件大小通过os.path.getsize获取，单位为字节。
        - 内部依赖、外部依赖和反向依赖会排序后用逗号分隔，空集合显示为"-"。
        - 点分名称为None时显示为"-"。

        Returns:
            str: 格式化的Markdown表格行字符串。

        ==========================================

        Convert the current node's information into a row of Markdown table, including module identifier, dotted name, size and dependency information.

        Conversion logic:
        - File size is obtained via os.path.getsize, in bytes.
        - Internal dependencies, external dependencies and reverse dependencies are sorted and separated by commas, empty sets are displayed as "-".
        - Dotted name is displayed as "-" when it is None.

        Returns:
            str: Formatted Markdown table row string.
        """
        size: int = os.path.getsize(self.path)
        internal: str = ", ".join([f"`{m}`" for m in sorted(self.imports_internal)]) or "-"
        external: str = ", ".join([f"`{m}`" for m in sorted(self.imports_external)]) or "-"
        imported_by: str = ", ".join([f"`{m}`" for m in sorted(self.imported_by)]) or "-"
        dotted: str = self.dotted_name or "-"

        return f"| `{self.module_id}` | `{dotted}` | {size} | {internal} | {external} | {imported_by} |"

class DependencyAnalyzer:
    """
    依赖分析器主类（面向对象实现），用于扫描Python项目、解析依赖关系并生成分析报告。

    核心功能包括：遍历指定根目录收集Python文件、生成模块唯一标识、解析AST提取导入依赖、
    构建正向/反向依赖关系、检测循环依赖，以及生成结构化Markdown报告。特别优化了对
    drivers/、libs/和tasks/目录的解析逻辑，即使缺少__init__.py也视为有效包；同时支持
    强制添加main.py对特定目录__init__.py的依赖关系。

    Attributes:
        root (str): 分析的项目根目录（绝对路径）。
        out_md (str): 输出Markdown报告的文件路径，默认值为"dependencies.md"。
        verbose (bool): 是否打印过程日志，默认值为True。
        module_map (Dict[str, str]): 模块标识映射表，key为module_id，value为文件绝对路径。
        dotted_map (Dict[str, str]): 点分名称映射表，key为module_id，value为模块的点分名称。
        nodes (Dict[str, FileNode]): 模块节点集合，key为module_id，value为FileNode实例。
        fixed_packages (Set[str]): 固定包目录集合，包含"drivers"、"libs"、"tasks"，放宽__init__.py检查。
        forced_deps_module_ids (List[str]): 需要被main.py强制依赖的模块标识列表，对应特定__init__.py文件。

    Methods:
        __init__(root: str, out_md: str = "dependencies.md", verbose: bool = True) -> None: 初始化分析器实例。
        scan_files() -> None: 扫描根目录收集Python文件，构建module_map。
        _compute_dotted_name(rel_noext: str, abs_path: str) -> Optional[str]: 计算模块的点分名称，处理固定包目录。
        build_module_map() -> None: 构建FileNode实例集合，填充nodes和dotted_map。
        _parse_imports_from_ast(tree: ast.AST, cur_module_id: str) -> Tuple[Set[str], Set[str]]: 从AST树提取导入依赖，区分内部/外部模块。
        _resolve_name_to_module(fullname: str) -> Optional[str]: 将导入名解析为项目内的module_id，优化固定包解析。
        parse_all_files() -> None: 解析所有Python文件的AST，收集依赖关系到FileNode。
        _add_main_forced_deps() -> None: 强制添加main.py对特定__init__.py的依赖（若文件存在）。
        link_reverse() -> None: 构建反向依赖关系（填充imported_by字段）。
        find_cycles() -> List[List[str]]: 检测项目中的循环依赖，返回循环路径列表。
        export_markdown(cycles: Optional[List[List[str]]] = None) -> None: 生成Markdown格式的依赖分析报告。
        run() -> None: 一键运行完整分析流程（扫描→构建→解析→添加强制依赖→反向链接→循环检测→导出报告）。

    Notes:
        - module_id格式为相对路径（不含.py后缀，使用/分隔，如"drivers/uart"），确保跨平台一致性。
        - 固定包目录（drivers/libs/tasks）下的模块无需__init__.py即可生成点分名称。
        - 强制依赖仅针对main.py（module_id为"main"），目标为三个固定目录的__init__.py。
        - 解析文件时若遇到语法错误，会跳过该文件并在verbose模式下打印错误信息。

    ==========================================

    Object-oriented main class for dependency analyzer, used to scan Python projects, parse dependencies and generate analysis reports.

    Core functions include: traversing the specified root directory to collect Python files, generating unique module identifiers,
    parsing AST to extract import dependencies, building forward/reverse dependency relationships, detecting cyclic dependencies,
    and generating structured Markdown reports. It is specially optimized for parsing drivers/, libs/, and tasks/ directories,
    treating them as valid packages even without __init__.py; it also supports forcing main.py to depend on specific __init__.py files.

    Attributes:
        root (str): Absolute path of the project root directory for analysis.
        out_md (str): File path for output Markdown report, default is "dependencies.md".
        verbose (bool): Whether to print process logs, default is True.
        module_map (Dict[str, str]): Module identifier mapping table, key is module_id, value is absolute file path.
        dotted_map (Dict[str, str]): Dotted name mapping table, key is module_id, value is dotted name of the module.
        nodes (Dict[str, FileNode]): Collection of module nodes, key is module_id, value is FileNode instance.
        fixed_packages (Set[str]): Set of fixed package directories, including "drivers", "libs", "tasks", relaxing __init__.py check.
        forced_deps_module_ids (List[str]): List of module IDs that main.py must depend on, corresponding to specific __init__.py files.

    Methods:
        __init__(root: str, out_md: str = "dependencies.md", verbose: bool = True) -> None: Initialize analyzer instance.
        scan_files() -> None: Scan root directory to collect Python files and build module_map.
        _compute_dotted_name(rel_noext: str, abs_path: str) -> Optional[str]: Compute dotted name of module, handle fixed package directories.
        build_module_map() -> None: Build collection of FileNode instances, populate nodes and dotted_map.
        _parse_imports_from_ast(tree: ast.AST, cur_module_id: str) -> Tuple[Set[str], Set[str]]: Extract import dependencies from AST, distinguish internal/external modules.
        _resolve_name_to_module(fullname: str) -> Optional[str]: Resolve import name to module_id in the project, optimize fixed package parsing.
        parse_all_files() -> None: Parse AST of all Python files, collect dependencies into FileNode.
        _add_main_forced_deps() -> None: Force add main.py's dependency on specific __init__.py (if file exists).
        link_reverse() -> None: Build reverse dependency relationships (populate imported_by field).
        find_cycles() -> List[List[str]]: Detect cyclic dependencies in the project, return list of cycle paths.
        export_markdown(cycles: Optional[List[List[str]]] = None) -> None: Generate dependency analysis report in Markdown format.
        run() -> None: One-click run of the complete analysis process (scan→build→parse→add forced deps→reverse link→cycle detect→export report).

    Notes:
        - module_id is in relative path format (without .py suffix, using / as separator, e.g., "drivers/uart") to ensure cross-platform consistency.
        - Modules in fixed package directories (drivers/libs/tasks) can generate dotted names without __init__.py.
        - Forced dependencies only target main.py (module_id is "main"), with targets being __init__.py of three fixed directories.
        - If syntax errors are encountered during file parsing, the file will be skipped and errors printed in verbose mode.
    """

    def __init__(
        self, root: str, out_md: str = "dependencies.md", verbose: bool = True
    ) -> None:
        """
        初始化依赖分析器实例，设置根目录、输出路径、日志模式，并初始化核心映射结构。

        Args:
            root (str): 项目根目录路径（支持相对路径或绝对路径，内部会转换为绝对路径）。
            out_md (str, optional): 输出Markdown报告的路径，默认值为"dependencies.md"。
            verbose (bool, optional): 是否启用过程日志打印，默认值为True。

        ==========================================

        Initialize dependency analyzer instance, set root directory, output path, log mode, and initialize core mapping structures.

        Args:
            root (str): Project root directory path (supports relative or absolute path, converted to absolute path internally).
            out_md (str, optional): Path for output Markdown report, default is "dependencies.md".
            verbose (bool, optional): Whether to enable process log printing, default is True.
        """
        self.root: str = os.path.abspath(root)  # 根目录绝对路径 (Absolute path of root directory)
        self.out_md: str = out_md  # 输出 Markdown 文件路径 (Output Markdown file path)
        self.verbose: bool = verbose  # 日志打印开关 (Log printing switch)
        self.module_map: Dict[str, str] = {}  # module_id -> absolute path (模块标识到绝对路径的映射)
        self.dotted_map: Dict[str, str] = {}  # module_id -> dotted_name (模块标识到点分名称的映射)
        self.nodes: Dict[str, FileNode] = {}  # module_id -> FileNode (模块标识到节点实例的映射)
        # 固定的包目录，确保这些目录下的结构被正确解析 (Fixed package directories to ensure correct parsing of their structures)
        self.fixed_packages: Set[str] = {"drivers", "libs", "tasks"}
        # 需要被main.py依赖的特定__init__.py的module_id (Module IDs of specific __init__.py that main.py must depend on)
        self.forced_deps_module_ids: List[str] = [
            "drivers/__init__",
            "libs/__init__",
            "tasks/__init__",
        ]

    # ---------- 扫描与模块标识 ----------
    def scan_files(self) -> None:
        """
        遍历项目根目录，收集所有有效Python文件并构建module_map映射表。

        扫描逻辑：
        1. 排除隐藏目录（以.开头）和__pycache__目录；
        2. 仅保留后缀为.py的文件；
        3. 为每个文件生成module_id（相对路径，不含.py后缀，使用/分隔）；
        4. 将module_id与文件绝对路径的映射存入module_map。

        日志输出：在verbose模式下打印扫描进度和找到的Python文件数量。

        Returns:
            None

        ==========================================

        Traverse the project root directory, collect all valid Python files and build module_map.

        Scanning logic:
        1. Exclude hidden directories (starting with .) and __pycache__ directory;
        2. Only retain files with .py suffix;
        3. Generate module_id for each file (relative path, without .py suffix, using / as separator);
        4. Store the mapping of module_id to absolute file path in module_map.

        Log output: Print scanning progress and number of found Python files in verbose mode.

        Returns:
            None
        """
        if self.verbose:
            print(f"[scan] scanning {self.root} ...")
        root_len: int = len(self.root.rstrip(os.sep)) + 1
        for dirpath, dirnames, filenames in os.walk(self.root):
            # 排除 __pycache__ 等不需要的目录 (Exclude unwanted directories like __pycache__)
            dirnames[:] = [
                d for d in dirnames if not d.startswith(".") and d != "__pycache__"
            ]
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                full: str = os.path.join(dirpath, fname)
                rel: str = full[root_len:]  # 相对路径（含文件名）(Relative path including filename)
                # module_id 使用 unix 风格分隔符，不含 .py (module_id uses Unix-style separator, without .py)
                rel_noext: str = rel[:-3].replace(os.sep, "/")
                # 记录 module map (Record module map)
                self.module_map[rel_noext] = full
        if self.verbose:
            print(f"[scan] found {len(self.module_map)} python files")

    def _compute_dotted_name(self, rel_noext: str, abs_path: str) -> Optional[str]:
        """
        内部方法：根据模块的相对路径（不含后缀）计算其点分名称（如"drivers.uart"）。

        特殊处理逻辑：
        1. 若路径片段属于fixed_packages（drivers/libs/tasks），即使缺少__init__.py也视为有效包；
        2. 非固定包目录需存在__init__.py才视为有效包，否则返回None；
        3. 逐层拼接有效包的目录名称，最终形成点分模块名。

        Args:
            rel_noext (str): 模块的相对路径（不含.py后缀，使用/分隔）。
            abs_path (str): 模块文件的绝对路径，用于验证__init__.py是否存在。

        Returns:
            Optional[str]: 成功解析的点分名称，解析失败则返回None。

        ==========================================

        Internal method: Compute the dotted name (e.g., "drivers.uart") based on the module's relative path (without suffix).

        Special handling logic:
        1. If path segment belongs to fixed_packages (drivers/libs/tasks), treat it as a valid package even without __init__.py;
        2. Non-fixed package directories require __init__.py to be a valid package, otherwise return None;
        3. Splice directory names of valid packages layer by layer to form the dotted module name.

        Args:
            rel_noext (str): Module's relative path (without .py suffix, using / as separator).
            abs_path (str): Absolute path of the module file, used to verify if __init__.py exists.

        Returns:
            Optional[str]: Successfully parsed dotted name, None if parsing fails.
        """
        parts: List[str] = rel_noext.split("/")
        if not parts:
            return None

        cur: str = self.root
        dotted_parts: List[str] = []
        is_inside_fixed_package: bool = False

        for i, p in enumerate(parts[:-1]):  # 逐层检查目录是否为包 (Check if directory is a package layer by layer)
            cur = os.path.join(cur, p)
            init_f: str = os.path.join(cur, "__init__.py")

            # 检查是否在固定包目录内 (Check if inside fixed package directory)
            if p in self.fixed_packages:
                is_inside_fixed_package = True

            # 对于固定包目录内的模块，放宽__init__.py检查 (Relax __init__.py check for modules inside fixed packages)
            if not os.path.exists(init_f) and not is_inside_fixed_package:
                # 非固定包目录且没有__init__.py，不构成完整包树 (Non-fixed package directory without __init__.py, does not form a complete package tree)
                return None

            dotted_parts.append(p)

        # 添加最后一部分（模块名）(Add the last part: module name)
        dotted_parts.append(parts[-1])
        return ".".join(dotted_parts)

    def build_module_map(self) -> None:
        """
        构建模块节点集合（nodes）和点分名称映射表（dotted_map）。

        处理流程：
        1. 遍历module_map，为每个module_id创建FileNode实例；
        2. 调用_compute_dotted_name生成模块的点分名称；
        3. 特殊处理固定包目录下的__init__.py：将其点分名称修正为包名本身（如"drivers.__init__"→"drivers"）；
        4. 将FileNode实例存入nodes，点分名称存入dotted_map。

        Returns:
            None

        ==========================================

        Build module node collection (nodes) and dotted name mapping table (dotted_map).

        Processing flow:
        1. Traverse module_map and create FileNode instance for each module_id;
        2. Call _compute_dotted_name to generate the module's dotted name;
        3. Special handling of __init__.py under fixed package directories: correct its dotted name to the package name itself (e.g., "drivers.__init__"→"drivers");
        4. Store FileNode instances in nodes and dotted names in dotted_map.

        Returns:
            None
        """
        for module_id, abs_path in sorted(self.module_map.items()):
            dotted: Optional[str] = self._compute_dotted_name(module_id, abs_path)
            node: FileNode = FileNode(module_id=module_id, path=abs_path, dotted_name=dotted)

            # 对于固定包的__init__.py，确保能被正确识别 (Ensure correct identification of __init__.py in fixed packages)
            parts: List[str] = module_id.split("/")
            if (
                len(parts) >= 2
                and parts[-1] == "__init__"
                and parts[-2] in self.fixed_packages
            ):
                # 为固定包的__init__.py添加额外的dotted_name（包名本身）(Add additional dotted_name for __init__.py of fixed packages: package name itself)
                package_name: str = parts[-2]
                if not node.dotted_name:
                    node.dotted_name = package_name
                else:
                    node.dotted_name = node.dotted_name.replace(f".__init__", "")

            self.nodes[module_id] = node
            self.dotted_map[module_id] = node.dotted_name

    # ---------- 解析 AST，收集导入 ----------
    def _parse_imports_from_ast(
        self, tree: ast.AST, cur_module_id: str
    ) -> Tuple[Set[str], Set[str]]:
        """
        内部方法：从Python抽象语法树（AST）中提取导入语句，区分内部依赖和外部依赖。

        支持解析的导入类型：
        1. 绝对导入：`import a.b as c` 和 `from a.b import c`；
        2. 相对导入：`from ..a import b`（基于当前模块的点分名称解析）；
        3. 固定包优化：优先解析fixed_packages下的模块，支持直接匹配别名。

        依赖区分规则：
        - 内部依赖：能解析为项目内module_id的导入；
        - 外部依赖：无法解析或属于第三方库的导入。

        Args:
            tree (ast.AST): 解析后的Python抽象语法树。
            cur_module_id (str): 当前解析文件的module_id，用于解析相对导入。

        Returns:
            Tuple[Set[str], Set[str]]: 第一个元素为内部依赖的module_id集合，第二个元素为外部依赖的模块名集合。

        ==========================================

        Internal method: Extract import statements from Python Abstract Syntax Tree (AST), distinguish internal and external dependencies.

        Supported import types:
        1. Absolute import: `import a.b as c` and `from a.b import c`;
        2. Relative import: `from ..a import b` (parsed based on the dotted name of the current module);
        3. Fixed package optimization: Prioritize parsing modules under fixed_packages, support direct alias matching.

        Dependency distinction rules:
        - Internal dependencies: Imports that can be resolved to module_id in the project;
        - External dependencies: Imports that cannot be resolved or belong to third-party libraries.

        Args:
            tree (ast.AST): Parsed Python abstract syntax tree.
            cur_module_id (str): module_id of the current parsed file, used to parse relative imports.

        Returns:
            Tuple[Set[str], Set[str]]: The first element is the set of module_ids for internal dependencies, the second is the set of module names for external dependencies.
        """
        internal: Set[str] = set()
        external: Set[str] = set()
        cur_node: Optional[FileNode] = self.nodes.get(cur_module_id)
        cur_dotted: Optional[str] = cur_node.dotted_name if cur_node else None

        for node in ast.walk(tree):
            # 处理 `import a.b as c` (Handle `import a.b as c`)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name: str = alias.name  # 形如 pkg.sub.module 或 pkg (Format like pkg.sub.module or pkg)
                    resolved: Optional[str] = self._resolve_name_to_module(name)
                    if resolved:
                        internal.add(resolved)
                    else:
                        external.add(name)

            # 处理 `from x import y` (Handle `from x import y`)
            elif isinstance(node, ast.ImportFrom):
                module: Optional[str] = node.module  # 形如 'pkg.sub' 或 None (Format like 'pkg.sub' or None)
                level: int = node.level  # 0 表示绝对导入，>0 表示相对导入 (0 for absolute import, >0 for relative import)

                # 计算实际被导入的模块基名 (Calculate the base name of the actually imported module)
                base_candidates: List[str] = []
                if level and level > 0:
                    # 相对导入，基于当前模块的dotted_name解析 (Relative import, parsed based on the dotted name of the current module)
                    if cur_dotted:
                        comps: List[str] = cur_dotted.split(".")
                    else:
                        comps: List[str] = cur_module_id.split("/")

                    # 计算上溯层级 (Calculate upward hierarchy)
                    if level <= len(comps):
                        base: List[str] = comps[:-level]
                    else:
                        base: List[str] = []

                    if module:
                        base = base + module.split(".")

                    if base:
                        candidate: str = ".".join(base)
                        base_candidates.append(candidate)
                else:
                    # 绝对导入 (Absolute import)
                    if module:
                        base_candidates.append(module)

                # 解析每个导入的名称 (Parse each imported name)
                for alias in node.names:
                    alias_name: str = alias.name
                    resolved_any: bool = False

                    # 优先尝试固定包的特殊解析 (Prioritize special parsing of fixed packages)
                    if module in self.fixed_packages:
                        fixed_candidate: str = f"{module}/{alias_name}"
                        if fixed_candidate in self.module_map:
                            internal.add(fixed_candidate)
                            resolved_any = True
                        else:
                            # 尝试固定包中的__init__.py (Try __init__.py in fixed packages)
                            fixed_init_candidate: str = f"{module}/{alias_name}/__init__"
                            if fixed_init_candidate in self.module_map:
                                internal.add(fixed_init_candidate)
                                resolved_any = True

                    # 常规解析 (Regular parsing)
                    if not resolved_any and base_candidates:
                        for base in base_candidates:
                            combos: List[str] = []
                            if base:
                                combos.append(f"{base}.{alias_name}")
                                combos.append(base)
                            else:
                                combos.append(alias_name)

                            for combo in combos:
                                r: Optional[str] = self._resolve_name_to_module(combo)
                                if r:
                                    internal.add(r)
                                    resolved_any = True
                                    break
                            if resolved_any:
                                break

                    if not resolved_any:
                        # 尝试直接解析别名作为固定包下的模块 (Try to directly parse alias as module under fixed packages)
                        for pkg in self.fixed_packages:
                            candidate: str = f"{pkg}/{alias_name}"
                            if candidate in self.module_map:
                                internal.add(candidate)
                                resolved_any = True
                                break
                            # 检查是否为包内的__init__.py (Check if it's __init__.py in the package)
                            candidate_init: str = f"{pkg}/{alias_name}/__init__"
                            if candidate_init in self.module_map:
                                internal.add(candidate_init)
                                resolved_any = True
                                break

                    if not resolved_any:
                        # 无法解析为内部模块 (Cannot be resolved as internal module)
                        if module:
                            external.add(f"{module}.{alias_name}")
                        else:
                            external.add(alias_name)

        return internal, external

    def _resolve_name_to_module(self, fullname: str) -> Optional[str]:
        """
        内部方法：将导入名（点分格式，如"drivers.uart"）解析为项目内的module_id。

        解析优先级（从高到低）：
        1. 固定包前缀匹配：优先解析fixed_packages下的模块，点分转路径格式；
        2. 通用前缀匹配：拆分导入名为多级前缀，尝试匹配module_id或包的__init__.py；
        3. 固定包顶层匹配：直接匹配fixed_packages中的包（如"drivers"→"drivers/__init__"）。

        Args:
            fullname (str): 导入名（点分格式，如"a.b.c"或"drivers"）。

        Returns:
            Optional[str]: 匹配到的module_id，无匹配则返回None。

        ==========================================

        Internal method: Resolve import name (dotted format, e.g., "drivers.uart") to module_id in the project.

        Parsing priority (from high to low):
        1. Fixed package prefix matching: Prioritize parsing modules under fixed_packages, convert dotted to path format;
        2. General prefix matching: Split import name into multi-level prefixes, try to match module_id or package's __init__.py;
        3. Fixed package top-level matching: Directly match packages in fixed_packages (e.g., "drivers"→"drivers/__init__").

        Args:
            fullname (str): Import name (dotted format, e.g., "a.b.c" or "drivers").

        Returns:
            Optional[str]: Matched module_id, None if no match.
        """
        if not fullname:
            return None

        # 首先检查是否是固定包下的模块 (First check if it's a module under fixed packages)
        for pkg in self.fixed_packages:
            if fullname.startswith(f"{pkg}."):
                # 将点分表示转换为路径表示 (Convert dotted representation to path representation)
                rel_path: str = fullname.replace(f"{pkg}.", f"{pkg}/").replace(".", "/")
                # 检查是否存在该模块 (Check if the module exists)
                if rel_path in self.module_map:
                    return rel_path
                # 检查是否存在该包的__init__.py (Check if __init__.py of the package exists)
                init_path: str = f"{rel_path}/__init__"
                if init_path in self.module_map:
                    return init_path

        # 通用解析逻辑 (General parsing logic)
        parts: List[str] = fullname.split(".")
        candidates: List[str] = []
        for cut in range(len(parts), 0, -1):
            left: List[str] = parts[:cut]
            rel_path: str = "/".join(left)
            candidates.append(rel_path)

        # 尝试匹配候选 (Try to match candidates)
        for cand in candidates:
            if cand in self.module_map:
                return cand
            # 检查是否为包的__init__.py (Check if it's __init__.py of the package)
            alt: str = cand + "/__init__"
            if alt in self.module_map:
                return alt

        # 特别处理固定包的顶层导入 (Special handling of top-level imports for fixed packages)
        if fullname in self.fixed_packages:
            # 检查该包的__init__.py (Check if __init__.py of the package exists)
            init_path: str = f"{fullname}/__init__"
            if init_path in self.module_map:
                return init_path

        return None

    def parse_all_files(self) -> None:
        """
        解析项目中所有Python文件的AST，提取依赖关系并写入对应的FileNode实例。

        处理流程：
        1. 遍历nodes中的每个FileNode实例；
        2. 读取文件内容并解析为AST（遇到语法错误则跳过并打印日志）；
        3. 调用_parse_imports_from_ast提取内部/外部依赖；
        4. 将依赖关系写入FileNode的imports_internal和imports_external字段。

        日志输出：在verbose模式下打印解析进度、错误信息和结果。

        Returns:
            None

        ==========================================

        Parse AST of all Python files in the project, extract dependencies and write to corresponding FileNode instances.

        Processing flow:
        1. Traverse each FileNode instance in nodes;
        2. Read file content and parse to AST (skip and print log if syntax error occurs);
        3. Call _parse_imports_from_ast to extract internal/external dependencies;
        4. Write dependencies to imports_internal and imports_external fields of FileNode.

        Log output: Print parsing progress, error messages and results in verbose mode.

        Returns:
            None
        """
        if self.verbose:
            print("[parse] parsing files and resolving imports ...")
        for module_id, node in self.nodes.items():
            try:
                with open(node.path, "r", encoding="utf-8") as f:
                    src: str = f.read()
                tree: ast.AST = ast.parse(src, filename=node.path)
            except Exception as e:
                if self.verbose:
                    print(f"[parse] failed to parse {node.path}: {e}")
                continue
            internal, external = self._parse_imports_from_ast(tree, module_id)
            node.imports_internal = internal
            node.imports_external = external

    # ---------- 强制添加main.py依赖 ----------
    def _add_main_forced_deps(self) -> None:
        """
        内部方法：强制添加main.py对特定__init__.py的依赖关系（若目标文件存在）。

        强制依赖规则：
        1. 目标依赖为forced_deps_module_ids中的module_id（对应drivers/libs/tasks的__init__.py）；
        2. 仅当main.py存在（module_id为"main"）且目标文件存在时才添加；
        3. 避免重复添加：若main.py已依赖目标模块，则不重复处理。

        日志输出：在verbose模式下打印添加结果（成功数量、跳过原因等）。

        Returns:
            None

        ==========================================

        Internal method: Force add main.py's dependency on specific __init__.py (if target file exists).

        Forced dependency rules:
        1. Target dependencies are module_ids in forced_deps_module_ids (corresponding to __init__.py of drivers/libs/tasks);
        2. Add only if main.py exists (module_id is "main") and target file exists;
        3. Avoid duplicate addition: Do not reprocess if main.py already depends on the target module.

        Log output: Print addition results (success count, skip reason, etc.) in verbose mode.

        Returns:
            None
        """
        main_module_id: str = "main"
        # 检查main.py是否存在 (Check if main.py exists)
        if main_module_id not in self.nodes:
            if self.verbose:
                print(
                    f"[force-dep] main.py not found (module_id: {main_module_id}), skip forced dependencies"
                )
            return

        main_node: FileNode = self.nodes[main_module_id]
        added_count: int = 0

        # 遍历需要强制依赖的module_id (Traverse module_ids that need forced dependencies)
        for dep_module_id in self.forced_deps_module_ids:
            # 检查目标__init__.py是否存在 (Check if target __init__.py exists)
            if dep_module_id in self.nodes:
                # 避免重复添加依赖 (Avoid duplicate dependencies)
                if dep_module_id not in main_node.imports_internal:
                    main_node.imports_internal.add(dep_module_id)
                    added_count += 1
                    if self.verbose:
                        print(
                            f"[force-dep] added {dep_module_id} as dependency of {main_module_id}"
                        )

        if self.verbose and added_count > 0:
            print(
                f"[force-dep] successfully added {added_count} forced dependencies to main.py"
            )
        elif self.verbose:
            print(
                f"[force-dep] no forced dependencies added (target __init__.py files not found)"
            )

    # ---------- 反向链接与循环检测 ----------
    def link_reverse(self) -> None:
        """
        构建反向依赖关系，填充每个FileNode的imported_by字段。

        处理流程：
        1. 清空所有FileNode的imported_by字段（避免残留数据）；
        2. 遍历每个模块的正向依赖（imports_internal），为目标模块的imported_by添加当前模块ID；
        3. 包含强制添加的依赖关系，确保反向依赖完整性。

        作用：支持后续的被引用次数统计和循环依赖检测。

        Returns:
            None

        ==========================================

        Build reverse dependency relationships and populate the imported_by field of each FileNode.

        Processing flow:
        1. Clear the imported_by field of all FileNodes (avoid residual data);
        2. Traverse the forward dependencies (imports_internal) of each module, add current module ID to the imported_by of the target module;
        3. Include forced dependencies to ensure the integrity of reverse dependencies.

        Function: Support subsequent statistics of referenced times and cyclic dependency detection.

        Returns:
            None
        """
        # 清空 imported_by (Clear imported_by)
        for node in self.nodes.values():
            node.imported_by = set()
        # 构造反向关系（包含强制添加的依赖）(Build reverse relationships including forced dependencies)
        for module_id, node in self.nodes.items():
            for tgt in node.imports_internal:
                if tgt in self.nodes:
                    self.nodes[tgt].imported_by.add(module_id)

    def find_cycles(self) -> List[List[str]]:
        """
        检测项目中的循环依赖，返回所有循环路径的列表。

        实现原理：采用DFS（深度优先搜索）三色标记法：
        - WHITE：未访问；
        - GRAY：正在访问（处于当前DFS路径中）；
        - BLACK：已访问完毕。
        当搜索到GRAY节点时，说明找到循环路径，回溯构建完整循环。

        去重处理：通过字符串化循环路径（如"a->b->c->a"）避免重复记录。

        日志输出：在verbose模式下打印检测进度和找到的循环数量。

        Returns:
            List[List[str]]: 循环路径列表，每个子列表为一个循环（如["a", "b", "c", "a"]）。

        ==========================================

        Detect cyclic dependencies in the project and return a list of all cycle paths.

        Implementation principle: DFS (Depth-First Search) three-color marking method:
        - WHITE: Unvisited;
        - GRAY: Being visited (in the current DFS path);
        - BLACK: Visited completely.
        When a GRAY node is searched, it indicates a cycle path is found, and backtracking is performed to build the complete cycle.

        Deduplication: Avoid duplicate records by stringifying cycle paths (e.g., "a->b->c->a").

        Log output: Print detection progress and number of found cycles in verbose mode.

        Returns:
            List[List[str]]: List of cycle paths, each sublist is a cycle (e.g., ["a", "b", "c", "a"]).
        """
        if self.verbose:
            print("[cycles] detecting cycles ...")
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {m: WHITE for m in self.nodes}
        parent: Dict[str, Optional[str]] = {}
        cycles: List[List[str]] = []

        def dfs(u: str) -> None:
            color[u] = GRAY
            for v in self.nodes[u].imports_internal:
                if v not in self.nodes:
                    continue
                if color[v] == WHITE:
                    parent[v] = u
                    dfs(v)
                elif color[v] == GRAY:
                    # 找到回边，构造循环 (Found back edge, build cycle)
                    cycle: List[str] = [v]
                    cur: Optional[str] = u
                    while cur != v and cur in parent:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(v)
                    cycle.reverse()
                    # 去重 (Deduplication)
                    key: str = "->".join(cycle)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cycle)
            color[u] = BLACK

        seen_cycles: Set[str] = set()
        for node in self.nodes:
            if color[node] == WHITE:
                parent[node] = None
                dfs(node)
        if self.verbose:
            print(f"[cycles] found {len(cycles)} cycles")
        return cycles

    # ---------- 输出 Markdown ----------
    def export_markdown(self, cycles: Optional[List[List[str]]] = None) -> None:
        """
        生成Markdown格式的依赖分析报告，包含模块信息、依赖关系和循环检测结果。

        报告结构：
        1. 基本信息：根目录、文件数量、循环依赖数量、强制依赖说明；
        2. 模块依赖表：包含module_id、点分名称、文件大小、内部/外部依赖、被引用者；
        3. 循环依赖详情：列出所有检测到的循环路径；
        4. 被引用次数排行：Top20被引用最多的模块。

        格式处理：
        - 空依赖显示为"-"；
        - 模块标识使用`反引号`强调；
        - 表格采用Markdown标准格式。

        Args:
            cycles (Optional[List[List[str]]], optional): 循环依赖路径列表，由find_cycles生成，默认值为None。

        Returns:
            None

        ==========================================

        Generate dependency analysis report in Markdown format, including module information, dependencies and cycle detection results.

        Report structure:
        1. Basic information: Root directory, number of files, number of cyclic dependencies, forced dependency description;
        2. Module dependency table: Includes module_id, dotted name, file size, internal/external dependencies, and referrers;
        3. Cyclic dependency details: List all detected cycle paths;
        4. Referenced times ranking: Top20 most referenced modules.

        Format handling:
        - Empty dependencies are displayed as "-";
        - Module identifiers are emphasized with `backticks`;
        - Tables use standard Markdown format.

        Args:
            cycles (Optional[List[List[str]]], optional): List of cyclic dependency paths, generated by find_cycles, default is None.

        Returns:
            None
        """
        if self.verbose:
            print(f"[export] writing markdown to {self.out_md}")
        lines: List[str] = []
        lines.append("# Python 文件依赖分析报告\n")
        lines.append(f"- 根目录：`{self.root}`  \n")
        lines.append(f"- 文件数量：**{len(self.nodes)}**  \n")
        if cycles:
            lines.append(f"- 检测到循环依赖：**{len(cycles)}** 个（见下方）  \n")
        else:
            lines.append(f"- 检测到循环依赖：**0**  \n")
        # 新增：标注强制依赖逻辑说明 (New: Add forced dependency logic description)
        lines.append(
            f"- 强制依赖：若 `drivers/__init__.py`、`libs/__init__.py`、`tasks/__init__.py` 存在，则自动设为 `main.py` 的依赖  \n"
        )
        lines.append("\n---\n")
        lines.append("## 模块依赖表\n")
        lines.append(
            "（`module_id` 使用相对路径作为唯一标识；`dotted_name` 如果为包路径则为点分名）\n"
        )
        lines.append(
            "\n| Module (module_id) | Dotted name | Size (bytes) | Imports (internal) | Imports (external) | Imported-by |\n"
        )
        lines.append("|---|---:|---:|---|---|---|\n")
        for module_id in sorted(self.nodes):
            row: str = self.nodes[module_id].to_md_row()
            lines.append(row + "\n")
        # 循环依赖详情 (Cyclic dependency details)
        if cycles:
            lines.append("\n---\n")
            lines.append("## 循环依赖详情\n")
            for i, cyc in enumerate(cycles, 1):
                lines.append(f"- Cycle {i}: `{' -> '.join(cyc)}`  \n")
        # 被引用次数排行 (Referenced times ranking)
        lines.append("\n---\n")
        lines.append("## 被引用次数排行（Top 20）\n")
        counts: List[Tuple[str, int]] = sorted(
            ((m, len(n.imported_by)) for m, n in self.nodes.items()),
            key=lambda x: -x[1],
        )
        lines.append("| Module | Imported-by count |\n")
        lines.append("|---|---:|\n")
        for m, c in counts[:20]:
            lines.append(f"| `{m}` | {c} |\n")
        # 写文件 (Write to file)
        with open(self.out_md, "w", encoding="utf-8") as f:
            f.writelines(lines)
        if self.verbose:
            print("[export] done.")

    # ---------- 一键运行接口 ----------
    def run(self) -> None:
        """
        一键运行完整的依赖分析流程，按顺序执行所有核心步骤。

        执行顺序：
        1. scan_files：扫描Python文件，构建module_map；
        2. build_module_map：创建FileNode实例，构建nodes和dotted_map；
        3. parse_all_files：解析AST，提取依赖关系；
        4. _add_main_forced_deps：添加强制依赖（main.py→特定__init__.py）；
        5. link_reverse：构建反向依赖关系；
        6. find_cycles：检测循环依赖；
        7. export_markdown：生成Markdown分析报告。

        日志输出：在verbose模式下打印各步骤进度。

        Returns:
            None

        ==========================================

        One-click run of the complete dependency analysis process, executing all core steps in sequence.

        Execution order:
        1. scan_files: Scan Python files and build module_map;
        2. build_module_map: Create FileNode instances, build nodes and dotted_map;
        3. parse_all_files: Parse AST and extract dependencies;
        4. _add_main_forced_deps: Add forced dependencies (main.py→specific __init__.py);
        5. link_reverse: Build reverse dependency relationships;
        6. find_cycles: Detect cyclic dependencies;
        7. export_markdown: Generate Markdown analysis report.

        Log output: Print progress of each step in verbose mode.

        Returns:
            None
        """
        self.scan_files()
        self.build_module_map()
        self.parse_all_files()
        # 新增：在解析完原有依赖后、构建反向依赖前添加强制依赖 (New: Add forced dependencies after parsing original dependencies and before building reverse dependencies)
        self._add_main_forced_deps()
        self.link_reverse()
        cycles: List[List[str]] = self.find_cycles()
        self.export_markdown(cycles)

class MarkdownVisualizer:
    """
    更健壮的 Markdown → HTML 依赖关系可视化生成器。

    该类通过解析 Markdown 格式的依赖分析报告，提取模块信息及依赖关系，
    采用分层布局算法计算节点位置，生成包含 SVG 图形的 HTML 文件，实现
    依赖关系的可视化展示。特别优化了模块分组标识和循环依赖识别功能。

    修复点：
      - 使用按 '|' 列拆分的解析方式，兼容更多表格样式。
      - 同时利用 Imports(internal) 和 Imported-by 列推断完整边，避免单侧截断导致的缺边。
      - 修复 HTML 生成时的缩进混乱问题，确保输出代码格式整洁。
      - 纯标准库实现，不依赖第三方包。

    新增功能：
      - 模块分组视觉标识：通过颜色区分引导核心、板级配置、任务层、驱动层、公共库。
      - 多箭头防重叠：同一对节点间的多个依赖箭头自动分散排列。
      - 循环依赖标记：循环依赖中的节点采用红色背景高亮显示。

    Attributes:
        NODE_WIDTH (int): 模块节点的宽度（像素），默认300。
        NODE_HEIGHT (int): 模块节点的高度（像素），默认40。
        LAYER_V_SPACING (int): 分层布局中相邻层的垂直间距（像素），默认300。
        NODE_H_SPACING (int): 同一层内节点的水平间距（像素），默认150。
        MARGIN (int): SVG 画布的边缘间距（像素），默认30。
        ARROW_OFFSET (int): 箭头端点与节点的距离（像素），默认0。
        ARROW_SPACING (int): 多箭头间的分散间距（像素），默认20。
        GROUP_CONFIG (Dict[str, Tuple[Callable[[str], bool], str, str]]): 模块分组配置，键为分组名，值为(匹配函数, 边框色, 背景色)。
        edge_counter (Dict[Tuple[str, str], int]): 跟踪同一对节点间的箭头数量，用于解决重叠问题。
        md_path (str): 输入 Markdown 依赖报告的文件路径。
        nodes (Dict[str, Dict]): 模块信息字典，键为 module_id，值包含dotted、imports、external、imported_by字段。
        adj (Dict[str, Set[str]]): 邻接表，存储依赖关系（被依赖者 → 依赖者）。
        cycles (List[List[str]]): 循环依赖路径列表，每个子列表为一个循环。
        _canvas_w (int): SVG 画布宽度（像素），默认800。
        _canvas_h (int): SVG 画布高度（像素），默认600。

    Methods:
        __init__(md_path: str) -> None: 初始化可视化生成器实例。
        _read_md() -> List[str]: 读取 Markdown 文件内容，返回行列表。
        _clean_item(s: str) -> str: 清理模块标识字符串，移除反引号和省略后缀。
        _split_cell(cell: str) -> List[str]: 拆分表格单元格内容，提取依赖模块列表。
        _parse_md_table(lines: List[str]) -> None: 解析 Markdown 表格，提取模块信息和依赖关系。
        _compute_layers() -> Dict[int, List[str]]: 基于拓扑排序计算模块的分层布局。
        _layout_positions(layers: Dict[int, List[str]]) -> Dict[str, Tuple[float, float]]: 计算每个模块节点的坐标位置。
        _escape(s: str) -> str: 对字符串进行 HTML 转义，避免注入问题。
        _detect_cycles() -> None: 采用 DFS 三色标记法检测循环依赖。
        _get_group_style(module_id: str) -> Tuple[str, str]: 根据模块ID匹配分组样式，返回(边框色, 背景色)。
        _render_svg(positions: Dict[str, Tuple[float, float]]) -> str: 生成 SVG 图形字符串，包含箭头和节点。
        _assemble_html(svg: str, title: str) -> str: 组装完整的 HTML 文档，修复缩进格式。
        generate_html(out_html: str) -> None: 一键生成可视化 HTML 文件，包含完整流程执行。

    Notes:
        - 依赖关系箭头方向：从被依赖模块指向依赖它的模块（符合"上游支撑下游"直觉）。
        - 模块ID采用相对路径格式（如"drivers/__init__"），与依赖分析报告保持一致。
        - 循环依赖节点会覆盖分组样式，采用红色背景和边框突出显示。
        - 生成的 HTML 包含响应式样式，支持画布滚动查看大型依赖图。

    ==========================================

    Robust Markdown → HTML dependency visualization generator.

    This class parses Markdown-formatted dependency analysis reports, extracts module information and dependencies,
    calculates node positions using a layered layout algorithm, and generates HTML files containing SVG graphics to
    visualize dependency relationships. It specially optimizes module grouping identification and cyclic dependency detection.

    Fixes:
      - Uses '|' column splitting for parsing, compatible with more table styles.
      - Infers complete edges using both Imports(internal) and Imported-by columns to avoid missing edges due to one-sided truncation.
      - Fixes indentation chaos when generating HTML to ensure clean output code format.
      - Implemented with pure standard libraries, no third-party dependencies.

    New Features:
      - Module grouping visual identification: Distinguishes boot core, board config, task layer, driver layer, and common library by color.
      - Multi-arrow anti-overlap: Multiple dependency arrows between the same pair of nodes are automatically spaced out.
      - Cyclic dependency marking: Nodes in cyclic dependencies are highlighted with red backgrounds.

    Attributes:
        NODE_WIDTH (int): Width of module nodes in pixels, default 300.
        NODE_HEIGHT (int): Height of module nodes in pixels, default 40.
        LAYER_V_SPACING (int): Vertical spacing between adjacent layers in layered layout (pixels), default 300.
        NODE_H_SPACING (int): Horizontal spacing between nodes in the same layer (pixels), default 150.
        MARGIN (int): Edge margin of SVG canvas (pixels), default 30.
        ARROW_OFFSET (int): Distance between arrow endpoint and node (pixels), default 0.
        ARROW_SPACING (int): Spacing between multiple arrows (pixels), default 20.
        GROUP_CONFIG (Dict[str, Tuple[Callable[[str], bool], str, str]]): Module grouping configuration, key is group name, value is (matching function, border color, background color).
        edge_counter (Dict[Tuple[str, str], int]): Tracks the number of arrows between the same pair of nodes to solve overlap issues.
        md_path (str): File path of input Markdown dependency report.
        nodes (Dict[str, Dict]): Module information dictionary, key is module_id, value contains dotted, imports, external, imported_by fields.
        adj (Dict[str, Set[str]]): Adjacency list storing dependencies (dependent module → dependent module).
        cycles (List[List[str]]): List of cyclic dependency paths, each sublist is a cycle.
        _canvas_w (int): SVG canvas width in pixels, default 800.
        _canvas_h (int): SVG canvas height in pixels, default 600.

    Methods:
        __init__(md_path: str) -> None: Initialize the visualizer instance.
        _read_md() -> List[str]: Read Markdown file content and return line list.
        _clean_item(s: str) -> str: Clean module identifier string, remove backticks and ellipsis suffix.
        _split_cell(cell: str) -> List[str]: Split table cell content and extract dependency module list.
        _parse_md_table(lines: List[str]) -> None: Parse Markdown table and extract module information and dependencies.
        _compute_layers() -> Dict[int, List[str]]: Calculate layered layout of modules based on topological sorting.
        _layout_positions(layers: Dict[int, List[str]]) -> Dict[str, Tuple[float, float]]: Calculate coordinate positions of each module node.
        _escape(s: str) -> str: HTML-escape strings to avoid injection issues.
        _detect_cycles() -> None: Detect cyclic dependencies using DFS three-color marking method.
        _get_group_style(module_id: str) -> Tuple[str, str]: Match group style by module ID, return (border color, background color).
        _render_svg(positions: Dict[str, Tuple[float, float]]) -> str: Generate SVG graphic string containing arrows and nodes.
        _assemble_html(svg: str, title: str) -> str: Assemble complete HTML document with fixed indentation.
        generate_html(out_html: str) -> None: One-click generate visual HTML file, including complete process execution.

    Notes:
        - Dependency arrow direction: From dependent module to the module that depends on it (conforming to "upstream supports downstream" intuition).
        - Module ID uses relative path format (e.g., "drivers/__init__"), consistent with the dependency analysis report.
        - Cyclic dependency nodes override group styles and are highlighted with red backgrounds and borders.
        - Generated HTML includes responsive styles, supporting canvas scrolling to view large dependency graphs.
    """

    # 节点尺寸配置 (Node size configuration)
    NODE_WIDTH: int = 300
    NODE_HEIGHT: int = 40
    LAYER_V_SPACING: int = 300  # 增加层间距，给箭头更多空间 (Increase layer spacing for arrows)
    NODE_H_SPACING: int = 150  # 增加节点水平间距 (Increase horizontal node spacing)
    MARGIN: int = 30

    # 箭头参数配置 (Arrow parameter configuration)
    ARROW_OFFSET: int = 0  # 增大箭头与节点的距离 (Distance between arrow and node)
    ARROW_SPACING: int = 20  # 多个箭头之间的间距 (Spacing between multiple arrows)

    # 模块分组配置（分组名 → (匹配函数, 边框色, 背景色)）
    # Module grouping config (group name → (matching func, border color, background color))
    GROUP_CONFIG: Dict[str, Tuple[Callable[[str], bool], str, str]] = {
        "引导核心": (
            lambda mid: mid in ("boot", "main"),  # 精确匹配核心入口文件 (Exact match for core entry files)
            "#2563eb",  # 蓝色边框 (Blue border)
            "#eff6ff",  # 浅蓝色背景 (Light blue background)
        ),
        "板级配置": (
            lambda mid: mid in ("board", "conf"),  # 精确匹配配置文件 (Exact match for config files)
            "#7c3aed",  # 紫色边框 (Purple border)
            "#f5f3ff",  # 浅紫色背景 (Light purple background)
        ),
        "任务层": (
            lambda mid: mid.startswith("tasks/"),  # 匹配 tasks/ 目录下的文件 (Match files under tasks/)
            "#16a34a",  # 绿色边框 (Green border)
            "#ecfdf5",  # 浅绿色背景 (Light green background)
        ),
        "驱动层": (
            lambda mid: mid.startswith("drivers/"),  # 匹配 drivers/ 目录下的文件 (Match files under drivers/)
            "#ea580c",  # 橙色边框 (Orange border)
            "#fff7ed",  # 浅橙色背景 (Light orange background)
        ),
        "公共库": (
            lambda mid: mid.startswith("libs/"),  # 匹配 libs/ 目录下的文件 (Match files under libs/)
            "#0891b2",  # 青色边框 (Cyan border)
            "#ecfeff",  # 浅青色背景 (Light cyan background)
        ),
    }

    # 用于跟踪同一对节点间的箭头数量，解决重叠问题
    # Track arrow count between the same node pair to avoid overlap
    edge_counter: Dict[Tuple[str, str], int] = {}

    def __init__(self, md_path: str) -> None:
        """
        初始化 Markdown 依赖可视化生成器实例。

        初始化核心数据结构，存储输入文件路径、模块信息、依赖关系等基础数据，
        为后续解析和可视化流程做准备。

        Args:
            md_path (str): 输入 Markdown 依赖分析报告的文件路径（支持相对路径或绝对路径）。

        ==========================================

        Initialize Markdown dependency visualization generator instance.

        Initialize core data structures to store input file path, module information, dependencies and other basic data,
        preparing for subsequent parsing and visualization processes.

        Args:
            md_path (str): File path of input Markdown dependency analysis report (supports relative or absolute path).
        """
        self.md_path: str = md_path
        # module_id → { dotted, imports(set), external(set), imported_by(set) }
        self.nodes: Dict[str, Dict] = {}
        # 邻接表：被依赖者 → 依赖者 (Adjacency list: dependent module → module that depends on it)
        self.adj: Dict[str, Set[str]] = {}
        # 循环依赖路径列表 (List of cyclic dependency paths)
        self.cycles: List[List[str]] = []
        # 画布初始尺寸 (Initial canvas size)
        self._canvas_w: int = 800
        self._canvas_h: int = 600

    # ---------------- MD 解析部分 (MD Parsing Section) ----------------
    def _read_md(self) -> List[str]:
        """
        读取 Markdown 文件内容，返回按行分割的字符串列表。

        采用 UTF-8 编码读取文件，确保中文等特殊字符正确解析，每行末尾的换行符已去除。

        Returns:
            List[str]: Markdown 文件内容的行列表，每个元素对应一行内容。

        ==========================================

        Read Markdown file content and return a list of strings split by lines.

        Read file with UTF-8 encoding to ensure correct parsing of special characters like Chinese,
        newline characters at the end of each line are removed.

        Returns:
            List[str]: Line list of Markdown file content, each element corresponds to one line.
        """
        with open(self.md_path, "r", encoding="utf-8") as f:
            return f.readlines()

    def _clean_item(self, s: str) -> str:
        """
        清理模块标识字符串，移除格式符号和冗余内容。

        处理逻辑：
        1. 去除字符串前后的空白字符；
        2. 移除首尾的反引号（`）；
        3. 去除末尾的省略号及后续内容（如 ", ..."）。

        Args:
            s (str): 需要清理的原始字符串（通常来自 Markdown 表格单元格）。

        Returns:
            str: 清理后的纯模块标识字符串。

        ==========================================

        Clean module identifier string by removing format symbols and redundant content.

        Processing logic:
        1. Remove leading and trailing whitespace characters;
        2. Remove backticks (`) at the start and end;
        3. Remove ellipsis and subsequent content at the end (e.g., ", ...").

        Args:
            s (str): Raw string to be cleaned (usually from Markdown table cells).

        Returns:
            str: Cleaned pure module identifier string.
        """
        s = s.strip()
        if s.startswith("`") and s.endswith("`"):
            s = s[1:-1].strip()
        s = re.sub(r",\s*\.\.\..*$", "", s)
        return s

    def _split_cell(self, cell: str) -> List[str]:
        """
        拆分 Markdown 表格单元格内容，提取依赖模块列表。

        处理逻辑：
        1. 去除单元格前后空白，空内容或 "-" 直接返回空列表；
        2. 移除所有反引号和末尾省略号；
        3. 按逗号分割字符串，过滤空字符串后返回模块列表。

        Args:
            cell (str): Markdown 表格单元格的原始内容（如 "`drivers/__init__`, `libs/__init__`"）。

        Returns:
            List[str]: 提取的依赖模块列表，每个元素为清理后的模块ID。

        ==========================================

        Split Markdown table cell content and extract dependency module list.

        Processing logic:
        1. Remove leading and trailing whitespace from cell, return empty list for empty content or "-";
        2. Remove all backticks and trailing ellipsis;
        3. Split string by commas, filter empty strings and return module list.

        Args:
            cell (str): Raw content of Markdown table cell (e.g., "`drivers/__init__`, `libs/__init__`").

        Returns:
            List[str]: Extracted dependency module list, each element is a cleaned module ID.
        """
        cell = cell.strip()
        if cell in ("", "-"):
            return []
        cell = cell.replace("`", "")
        cell = re.sub(r",\s*\.\.\..*$", "", cell)
        parts = [p.strip() for p in cell.split(",") if p.strip()]
        return parts

    def _parse_md_table(self, lines: List[str]) -> None:
        """
        解析 Markdown 表格，提取模块信息和依赖关系。

        解析流程：
        1. 定位表格区域（以 "|" 开头且包含分隔线 "---" 的部分）；
        2. 逐行解析表格内容，提取 module_id、dotted_name、内部依赖、外部依赖、反向依赖；
        3. 构建 nodes 字典存储模块元信息；
        4. 基于 imports 和 imported_by 列构建邻接表（被依赖者 → 依赖者）。

        Args:
            lines (List[str]): Markdown 文件内容的行列表，由 _read_md() 方法提供。

        Returns:
            None

        ==========================================

        Parse Markdown table and extract module information and dependencies.

        Parsing process:
        1. Locate table area (part starting with "|" and containing separator "---");
        2. Parse table content line by line, extract module_id, dotted_name, internal dependencies, external dependencies, reverse dependencies;
        3. Build nodes dictionary to store module metadata;
        4. Build adjacency list (dependent module → module that depends on it) based on imports and imported_by columns.

        Args:
            lines (List[str]): Line list of Markdown file content, provided by _read_md() method.

        Returns:
            None
        """
        in_table: bool = False
        for i, ln in enumerate(lines):
            ln = ln.rstrip("\n")
            if not in_table:
                # 检测表格开始（包含分隔线的行）(Detect table start: line with separator)
                if ln.strip().startswith("|") and re.search(r"\|\s*-{3,}", ln):
                    in_table = True
                continue
            # 检测表格结束（非 "|" 开头的行）(Detect table end: line not starting with "|")
            if not ln.strip().startswith("|"):
                break
            # 拆分表格列（去除首尾的 "|"）(Split table columns: remove leading/trailing "|")
            cols = ln.split("|")[1:-1]
            cols = [c.strip() for c in cols]
            # 确保表格列数足够（至少6列）(Ensure sufficient table columns: at least 6)
            if len(cols) < 6:
                continue
            # 提取各列数据 (Extract column data)
            module_col: str = cols[0]
            dotted_col: str = cols[1]
            imports_internal_col: str = cols[3]
            imports_external_col: str = cols[4]
            imported_by_col: str = cols[5]

            # 清理并存储模块信息 (Clean and store module information)
            module_id: str = self._clean_item(module_col)
            dotted: str = self._clean_item(dotted_col)
            imports_internal: List[str] = self._split_cell(imports_internal_col)
            imports_external: List[str] = self._split_cell(imports_external_col)
            imported_by: List[str] = self._split_cell(imported_by_col)

            self.nodes[module_id] = {
                "dotted": dotted,
                "imports": set(imports_internal),
                "external": set(imports_external),
                "imported_by": set(imported_by),
            }

        # 初始化邻接表 (Initialize adjacency list)
        for m in self.nodes:
            self.adj[m] = set()

        # 基于 imports 列构建依赖关系（u依赖tgt → tgt被u依赖）
        # Build dependencies from imports column (u depends on tgt → tgt is depended by u)
        for u, props in self.nodes.items():
            for tgt in props["imports"]:
                if tgt in self.nodes:
                    self.adj[tgt].add(u)

        # 基于 imported_by 列补充依赖关系（u被importer依赖 → u→importer）
        # Supplement dependencies from imported_by column (u is depended by importer → u→importer)
        for u, props in self.nodes.items():
            for importer in props["imported_by"]:
                if importer in self.nodes:
                    self.adj[u].add(importer)

    # ---------------- 布局与 Cycle 检测部分 (Layout & Cycle Detection Section) ----------------
    def _compute_layers(self) -> Dict[int, List[str]]:
        """
        基于拓扑排序计算模块的分层布局，确定各模块所在的层级。

        实现逻辑：
        1. 计算每个节点的入度（被依赖次数）；
        2. 采用广度优先搜索（BFS），先将入度为0的节点放入第0层；
        3. 逐层处理节点，将其依赖的节点入度减1，入度为0时放入下一层；
        4. 循环依赖的节点会被放入最后一层。

        Returns:
            Dict[int, List[str]]: 分层结果字典，键为层索引（从0开始），值为该层的模块ID列表。

        ==========================================

        Calculate layered layout of modules based on topological sorting to determine the layer of each module.

        Implementation logic:
        1. Calculate in-degree (number of dependencies) for each node;
        2. Use Breadth-First Search (BFS), first put nodes with in-degree 0 into layer 0;
        3. Process nodes layer by layer, decrease in-degree of their dependent nodes by 1, put into next layer when in-degree is 0;
        4. Nodes with cyclic dependencies are put into the last layer.

        Returns:
            Dict[int, List[str]]: Layered result dictionary, key is layer index (starting from 0), value is module ID list of the layer.
        """
        # 初始化入度字典 (Initialize in-degree dictionary)
        indeg: Dict[str, int] = {u: 0 for u in self.adj}
        for u, vs in self.adj.items():
            for v in vs:
                indeg[v] = indeg.get(v, 0) + 1

        layers: Dict[int, List[str]] = {}
        # 入度为0的节点作为起始层 (Nodes with in-degree 0 as starting layer)
        q: List[str] = [u for u, d in indeg.items() if d == 0]
        placed: Set[str] = set()
        layer_idx: int = 0

        while q:
            # 存储当前层节点并排序 (Store current layer nodes and sort)
            layers[layer_idx] = sorted(q)
            placed.update(q)
            next_q: List[str] = []
            # 处理当前层节点的依赖关系 (Process dependencies of current layer nodes)
            for u in q:
                for v in self.adj.get(u, []):
                    indeg[v] -= 1
                    if indeg[v] == 0:
                        next_q.append(v)
            # 去重并排序，准备下一层 (Deduplicate, sort and prepare next layer)
            q = sorted(set(next_q))
            layer_idx += 1

        # 处理循环依赖的节点（未被放置的节点）(Process cyclic dependency nodes: unplaced nodes)
        remaining: List[str] = [u for u in self.adj if u not in placed]
        if remaining:
            layers[layer_idx] = sorted(remaining)

        return layers

    def _layout_positions(
        self, layers: Dict[int, List[str]]
    ) -> Dict[str, Tuple[float, float]]:
        """
        根据分层结果计算每个模块节点在 SVG 画布上的坐标位置。

        计算逻辑：
        1. 先计算画布总尺寸（基于最大层宽度和总高度）；
        2. 逐层计算节点位置：每层水平居中对齐，节点等间距分布；
        3. 节点坐标以中心为基准（便于后续绘制矩形和箭头）。

        Args:
            layers (Dict[int, List[str]]): 分层结果字典，由 _compute_layers() 方法提供。

        Returns:
            Dict[str, Tuple[float, float]]: 节点坐标字典，键为模块ID，值为 (中心x坐标, 中心y坐标)。

        ==========================================

        Calculate coordinate positions of each module node on the SVG canvas based on layered results.

        Calculation logic:
        1. First calculate total canvas size (based on maximum layer width and total height);
        2. Calculate node positions layer by layer: each layer is horizontally centered, nodes are equally spaced;
        3. Node coordinates are based on the center (facilitating subsequent rectangle and arrow drawing).

        Args:
            layers (Dict[int, List[str]]): Layered result dictionary, provided by _compute_layers() method.

        Returns:
            Dict[str, Tuple[float, float]]: Node coordinate dictionary, key is module ID, value is (center x, center y).
        """
        positions: Dict[str, Tuple[float, float]] = {}
        max_width: float = 0.0
        total_height: float = self.MARGIN * 2  # 上下边距 (Top and bottom margins)

        # 先计算画布总高度和最大宽度 (First calculate total canvas height and maximum width)
        for li, nodes in layers.items():
            layer_h: int = self.NODE_HEIGHT
            total_height += layer_h
            if li > 0:
                total_height += self.LAYER_V_SPACING
            # 计算当前层宽度 (Calculate current layer width)
            layer_w: float = len(nodes) * self.NODE_WIDTH + max(0, len(nodes) - 1) * self.NODE_H_SPACING
            if layer_w > max_width:
                max_width = layer_w

        # 确定画布最终宽度 (Determine final canvas width)
        canvas_w: float = max(300, max_width + self.MARGIN * 2)
        y: float = self.MARGIN  # 当前层的顶部y坐标 (Top y coordinate of current layer)

        # 计算每个节点的具体坐标 (Calculate specific coordinates for each node)
        for li in sorted(layers):
            nodes: List[str] = layers[li]
            layer_w: float = len(nodes) * self.NODE_WIDTH + max(0, len(nodes) - 1) * self.NODE_H_SPACING
            # 层的水平起始位置（居中对齐）(Horizontal start position of layer: center alignment)
            x0: float = (canvas_w - layer_w) / 2 + self.NODE_WIDTH / 2

            for i, m in enumerate(nodes):
                # 节点中心x坐标 (Node center x coordinate)
                cx: float = x0 + i * (self.NODE_WIDTH + self.NODE_H_SPACING)
                # 节点中心y坐标 (Node center y coordinate)
                cy: float = y + self.NODE_HEIGHT / 2
                positions[m] = (cx, cy)

            # 移动到下一层的起始y坐标 (Move to start y coordinate of next layer)
            y += self.NODE_HEIGHT + self.LAYER_V_SPACING

        # 更新画布尺寸 (Update canvas size)
        self._canvas_w = math.ceil(canvas_w)
        self._canvas_h = math.ceil(y + self.MARGIN)

        return positions

    def _escape(self, s: str) -> str:
        """
        对字符串进行 HTML 转义，避免特殊字符导致的渲染问题。

        转义的特殊字符包括：&、<、>、"、'，确保字符串可安全嵌入 HTML 文档中。

        Args:
            s (str): 需要转义的原始字符串（如模块ID、节点文本等）。

        Returns:
            str: HTML 转义后的安全字符串。

        ==========================================

        HTML-escape string to avoid rendering issues caused by special characters.

        Escaped special characters include: &, <, >, ", ', ensuring the string can be safely embedded in HTML documents.

        Args:
            s (str): Raw string to be escaped (e.g., module ID, node text).

        Returns:
            str: HTML-escaped safe string.
        """
        return html.escape(s)

    def _detect_cycles(self) -> None:
        """
        采用深度优先搜索（DFS）三色标记法检测项目中的循环依赖。

        标记定义：
        - WHITE（0）：未访问；
        - GRAY（1）：正在访问（处于当前 DFS 路径中）；
        - BLACK（2）：已访问完毕。

        检测逻辑：
        1. 遍历所有未访问节点，启动 DFS；
        2. 遇到 GRAY 节点时，说明找到循环路径，回溯构建完整循环；
        3. 通过字符串化路径去重，避免重复记录相同循环。

        Returns:
            None

        ==========================================

        Detect cyclic dependencies in the project using Depth-First Search (DFS) three-color marking method.

        Marking definition:
        - WHITE (0): Unvisited;
        - GRAY (1): Being visited (in current DFS path);
        - BLACK (2): Visited completely.

        Detection logic:
        1. Traverse all unvisited nodes and start DFS;
        2. When encountering a GRAY node, a cyclic path is found, backtrack to build the complete cycle;
        3. Deduplicate by stringifying paths to avoid recording duplicate cycles.

        Returns:
            None
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        # 初始化节点颜色（均为未访问）(Initialize node colors: all unvisited)
        color: Dict[str, int] = {n: WHITE for n in self.adj}
        # 记录节点的父节点，用于回溯构建循环 (Record parent nodes for backtracking to build cycles)
        parent: Dict[str, Optional[str]] = {}
        cycles: List[List[str]] = []
        # 已发现的循环路径（用于去重）(Discovered cyclic paths: for deduplication)
        seen: Set[str] = set()

        def dfs(u: str) -> None:
            """DFS 递归函数，检测循环并构建路径 (DFS recursive function to detect cycles and build paths)"""
            color[u] = GRAY
            # 遍历当前节点的所有依赖者 (Traverse all dependents of current node)
            for v in self.adj.get(u, []):
                if v not in color:
                    continue
                if color[v] == WHITE:
                    parent[v] = u
                    dfs(v)
                elif color[v] == GRAY:
                    # 找到循环，回溯构建路径 (Found cycle, backtrack to build path)
                    cur: Optional[str] = u
                    path: List[str] = [v]
                    while cur != v and cur in parent:
                        path.append(cur)
                        cur = parent[cur]
                    path.append(v)
                    path.reverse()
                    # 字符串化路径用于去重 (Stringify path for deduplication)
                    key: str = "->".join(path)
                    if key not in seen:
                        seen.add(key)
                        cycles.append(path)
            color[u] = BLACK

        # 对所有未访问节点启动 DFS (Start DFS for all unvisited nodes)
        for n in list(self.adj.keys()):
            if color[n] == WHITE:
                parent[n] = None
                dfs(n)

        self.cycles = cycles

    # ---------------- 分组样式匹配方法 (Group Style Matching Method) ----------------
    def _get_group_style(self, module_id: str) -> Tuple[str, str]:
        """
        根据模块ID匹配对应的分组样式，返回边框色和背景色。

        匹配逻辑：按 GROUP_CONFIG 中的顺序依次匹配，首个匹配的分组即为目标分组，
        若均不匹配则返回默认样式（深灰色边框，白色背景）。

        Args:
            module_id (str): 需要匹配分组的模块ID（如 "main"、"drivers/uart"）。

        Returns:
            Tuple[str, str]: 分组样式，第一个元素为边框色（十六进制字符串），第二个为背景色。

        ==========================================

        Match corresponding group style by module ID and return border color and background color.

        Matching logic: Match in the order of GROUP_CONFIG, the first matching group is the target group,
        return default style (dark gray border, white background) if no match.

        Args:
            module_id (str): Module ID to match group (e.g., "main", "drivers/uart").

        Returns:
            Tuple[str, str]: Group style, first element is border color (hex string), second is background color.
        """
        for name, (match_func, border_color, bg_color) in self.GROUP_CONFIG.items():
            if match_func(module_id):
                return (border_color, bg_color)
        # 默认样式（非分组模块）(Default style: non-grouped modules)
        return ("#333", "#ffffff")

    # ---------------- SVG 渲染部分 (SVG Rendering Section) ----------------
    def _render_svg(self, positions: Dict[str, Tuple[float, float]]) -> str:
        """
        基于节点坐标生成 SVG 图形字符串，包含箭头和模块节点。

        渲染流程：
        1. 定义箭头标记（marker），用于箭头端点；
        2. 绘制依赖边：根据邻接表绘制贝塞尔曲线箭头，多箭头自动分散；
        3. 绘制模块节点：根据分组样式和循环依赖状态绘制矩形和文本；
        4. 组装 SVG 字符串，包含命名空间和画布尺寸信息。

        Args:
            positions (Dict[str, Tuple[float, float]]: 节点坐标字典，由 _layout_positions() 方法提供。

        Returns:
            str: 完整的 SVG 图形字符串，可直接嵌入 HTML 文档。

        ==========================================

        Generate SVG graphic string based on node coordinates, including arrows and module nodes.

        Rendering process:
        1. Define arrow marker for arrow endpoints;
        2. Draw dependency edges: draw Bezier curve arrows based on adjacency list, multiple arrows are automatically spaced;
        3. Draw module nodes: draw rectangles and text based on group style and cyclic dependency status;
        4. Assemble SVG string with namespace and canvas size information.

        Args:
            positions (Dict[str, Tuple[float, float]: Node coordinate dictionary, provided by _layout_positions() method.

        Returns:
            str: Complete SVG graphic string, can be directly embedded in HTML documents.
        """
        svg_items: List[str] = []
        # 重置箭头计数器 (Reset arrow counter)
        self.edge_counter = {}

        # 1. 定义箭头标记 (Define arrow marker)
        svg_items.append(
            f"""<defs>
            <marker id="arrow" markerWidth="18" markerHeight="18" refX="16" refY="9" orient="auto">
                <path d="M0,0 L18,9 L0,18 z" fill="#555" />
            </marker>
        </defs>"""
        )

        # 2. 绘制依赖边 (Draw dependency edges)
        for u, vs in self.adj.items():
            if u not in positions:
                continue
            ux, uy = positions[u]

            # 对目标节点排序，确保箭头顺序一致 (Sort target nodes for consistent arrow order)
            sorted_vs: List[str] = sorted(vs)
            for v in sorted_vs:
                if v not in positions:
                    continue
                vx, vy = positions[v]

                # 跟踪同一对节点的箭头数量，计算偏移量 (Track arrow count for same node pair, calculate offset)
                edge_key: Tuple[str, str] = (u, v)
                self.edge_counter[edge_key] = self.edge_counter.get(edge_key, 0) + 1
                edge_index: int = self.edge_counter[edge_key] - 1

                # 多箭头时分散排列 (Space out multiple arrows)
                offset: float = 0.0
                if self.edge_counter[edge_key] > 1:
                    mid: float = (self.edge_counter[edge_key] - 1) / 2
                    offset = (edge_index - mid) * self.ARROW_SPACING

                # 计算箭头起点（远离源节点u）(Calculate arrow start point: away from source node u)
                if vx > ux + self.NODE_WIDTH / 4:  # 目标在右侧 (Target on the right)
                    start_x = ux + self.NODE_WIDTH / 2 - self.ARROW_OFFSET
                    start_y = uy + offset
                elif vx < ux - self.NODE_WIDTH / 4:  # 目标在左侧 (Target on the left)
                    start_x = ux - self.NODE_WIDTH / 2 + self.ARROW_OFFSET
                    start_y = uy + offset
                elif vy > uy:  # 目标在下方 (Target below)
                    start_x = ux + offset
                    start_y = uy + self.NODE_HEIGHT / 2 - self.ARROW_OFFSET
                else:  # 目标在上方 (Target above)
                    start_x = ux + offset
                    start_y = uy - self.NODE_HEIGHT / 2 + self.ARROW_OFFSET

                # 计算箭头终点（远离目标节点v）(Calculate arrow end point: away from target node v)
                if vx > ux + self.NODE_WIDTH / 4:  # 从右侧进入 (Enter from right)
                    end_x = vx - self.NODE_WIDTH / 2 + self.ARROW_OFFSET
                    end_y = vy + offset
                elif vx < ux - self.NODE_WIDTH / 4:  # 从左侧进入 (Enter from left)
                    end_x = vx + self.NODE_WIDTH / 2 - self.ARROW_OFFSET
                    end_y = vy + offset
                elif vy > uy:  # 从上方进入 (Enter from above)
                    end_x = vx + offset
                    end_y = vy - self.NODE_HEIGHT / 2 + self.ARROW_OFFSET
                else:  # 从下方进入 (Enter from below)
                    end_x = vx + offset
                    end_y = vy + self.NODE_HEIGHT / 2 - self.ARROW_OFFSET

                # 计算贝塞尔曲线控制点，使路径自然 (Calculate Bezier curve control points for natural path)
                dx: float = end_x - start_x
                dy: float = end_y - start_y
                if abs(dx) > abs(dy):  # 水平为主 (Horizontal main direction)
                    curve_factor: float = 0.4 if abs(dx) > 100 else 0.6
                    cx1 = start_x + dx * curve_factor
                    cy1 = start_y + dy * 0.1
                    cx2 = end_x - dx * curve_factor
                    cy2 = end_y - dy * 0.1
                else:  # 垂直为主 (Vertical main direction)
                    curve_factor: float = 0.4 if abs(dy) > 100 else 0.6
                    cx1 = start_x + dx * 0.1
                    cy1 = start_y + dy * curve_factor
                    cx2 = end_x - dx * 0.1
                    cy2 = end_y - dy * curve_factor

                # 绘制曲线箭头 (Draw curved arrow)
                path: str = f"M {start_x:.1f},{start_y:.1f} C {cx1:.1f},{cy1:.1f} {cx2:.1f},{cy2:.1f} {end_x:.1f},{end_y:.1f}"
                svg_items.append(
                    f'<path d="{path}" fill="none" stroke="#555" stroke-width="2.0" marker-end="url(#arrow)" />'
                )

        # 3. 绘制节点（应用分组样式）(Draw nodes with group styles)
        # 收集循环依赖中的节点 (Collect nodes in cyclic dependencies)
        cycle_nodes: Set[str] = set()
        for cyc in self.cycles:
            cycle_nodes.update(cyc)

        for m, pos in positions.items():
            cx, cy = pos
            # 节点左上角坐标 (Node top-left coordinates)
            x: float = cx - self.NODE_WIDTH / 2
            y: float = cy - self.NODE_HEIGHT / 2
            # 判断是否为循环依赖节点 (Check if node is in cyclic dependency)
            is_cycle: bool = m in cycle_nodes

            # 样式优先级：循环依赖 > 分组样式 > 默认样式 (Style priority: cyclic > group > default)
            if is_cycle:
                fill: str = "#ffecec"
                stroke: str = "#c33"
            else:
                stroke, fill = self._get_group_style(m)

            # 绘制节点矩形和文本 (Draw node rectangle and text)
            svg_items.append(f'<g class="node" data-id="{self._escape(m)}">')
            svg_items.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{self.NODE_WIDTH}" height="{self.NODE_HEIGHT}" rx="6" ry="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5" />'
            )
            # 文本过长时截断 (Truncate long text)
            display: str = m if len(m) <= 50 else (m[:46] + "...")
            svg_items.append(
                f'<text x="{(cx - self.NODE_WIDTH / 2) + 10:.1f}" y="{cy + 7:.1f}" font-family="sans-serif" font-size="14">{self._escape(display)}</text>'
            )
            svg_items.append("</g>")

        # 4. 组装SVG (Assemble SVG)
        svg_body: str = "\n".join(svg_items)
        svg: str = f'<svg width="{self._canvas_w}" height="{self._canvas_h}" viewBox="0 0 {self._canvas_w} {self._canvas_h}" xmlns="http://www.w3.org/2000/svg" role="img">\n{svg_body}\n</svg>'
        return svg

    # ---------------- HTML 组装部分 (HTML Assembly Section) ----------------
    def _assemble_html(self, svg: str, title: str) -> str:
        """
        组装完整的 HTML 文档，包含 SVG 图形和样式，修复缩进格式。

        文档结构：
        1. 标准 HTML5 文档声明和头部（字符集、标题、样式）；
        2. 页面主体：标题、循环依赖提示、分组图例、SVG 画布、说明文本；
        3. 响应式样式：支持画布滚动、节点和文本样式统一。

        缩进优化：采用 4 空格缩进，确保 HTML 代码结构清晰，符合前端规范。

        Args:
            svg (str): SVG 图形字符串，由 _render_svg() 方法提供。
            title (str): HTML 页面的标题（显示在浏览器标签栏）。

        Returns:
            str: 完整的 HTML 文档字符串，格式整洁可直接写入文件。

        ==========================================

        Assemble complete HTML document containing SVG graphics and styles, with fixed indentation.

        Document structure:
        1. Standard HTML5 document declaration and head (charset, title, styles);
        2. Page body: title, cyclic dependency prompt, group legend, SVG canvas, description text;
        3. Responsive styles: support canvas scrolling, unified node and text styles.

        Indentation optimization: Use 4-space indentation to ensure clear HTML code structure, conforming to front-end specifications.

        Args:
            svg (str): SVG graphic string, provided by _render_svg() method.
            title (str): HTML page title (displayed in browser tab).

        Returns:
            str: Complete HTML document string with clean format, can be directly written to file.
        """
        # 循环依赖提示（存在循环时显示）(Cyclic dependency prompt: displayed when cycles exist)
        cycle_note: str = ""
        if self.cycles:
            cycle_note = f'<p style="color:#a33">注意：检测到 {len(self.cycles)} 个循环依赖（部分节点）。循环节点用红色标注。</p>'

        # 分组图例（固定格式）(Group legend: fixed format)
        group_legend: str = '''
        <div class="group-legend" style="margin: 12px 0; padding: 8px; background: #f0f0f0; border-radius: 4px;">
            <p style="margin: 0 0 8px 0; font-weight: bold;">模块分组说明：</p>
            <ul style="margin: 0; padding-left: 20px; line-height: 1.6;">
                <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #2563eb; background: #eff6ff;"></span>引导核心：boot、main.py</li>
                <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #7c3aed; background: #f5f3ff;"></span>板级配置：board、conf</li>
                <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #16a34a; background: #ecfdf5;"></span>任务层：tasks/ 下所有任务文件</li>
                <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #ea580c; background: #fff7ed;"></span>驱动层：drivers/ 下所有驱动包</li>
                <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #0891b2; background: #ecfeff;"></span>公共库：libs/ 下所有工具库（logger/network 等）</li>
            </ul>
        </div>'''

        # 组装完整HTML（统一4空格缩进）(Assemble complete HTML with 4-space indentation)
        html_doc: str = f'''<!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>{html.escape(title)}</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial; 
                    padding: 16px; 
                }}
                .svg-wrap {{ 
                    border: 1px solid #ddd; 
                    overflow: auto; 
                    padding: 16px; 
                    background: #fafafa; 
                }}
                .legend {{ 
                    margin-top: 12px; 
                    font-size: 14px; 
                    color: #444; 
                }}
                .group-legend {{ 
                    font-size: 14px; 
                    color: #444; 
                }}
            </style>
        </head>
        <body>
            <h2>{html.escape(title)}</h2>
            {cycle_note}
            {group_legend}
            <div class="svg-wrap">{svg}</div>
            <div class="legend">
                <p><strong>说明：</strong>节点表示 module_id（相对路径或规范化名），箭头从被依赖模块指向依赖它的模块。环路节点用红色背景。</p>
            </div>
        </body>
        </html>'''
        return html_doc

    # ---------------- 对外 API (Public API) ----------------
    def generate_html(self, out_html: str) -> None:
        """
        一键生成依赖关系可视化 HTML 文件，执行完整的解析-布局-渲染流程。

        执行顺序：
        1. 读取 Markdown 报告内容；
        2. 解析表格提取模块信息和依赖关系；
        3. 检测循环依赖；
        4. 计算模块分层布局和坐标位置；
        5. 生成 SVG 图形；
        6. 组装 HTML 文档并写入文件。

        辅助处理：自动创建输出目录（若不存在），确保文件正常写入。

        Args:
            out_html (str): 输出 HTML 文件的路径（支持相对路径或绝对路径）。

        Returns:
            None

        ==========================================

        One-click generate dependency visualization HTML file, executing complete parse-layout-render process.

        Execution order:
        1. Read Markdown report content;
        2. Parse table to extract module information and dependencies;
        3. Detect cyclic dependencies;
        4. Calculate module layered layout and coordinate positions;
        5. Generate SVG graphics;
        6. Assemble HTML document and write to file.

        Auxiliary processing: Automatically create output directory (if not exists) to ensure normal file writing.

        Args:
            out_html (str): Output HTML file path (supports relative or absolute path).

        Returns:
            None
        """
        # 1. 读取 MD 文件 (Read MD file)
        lines: List[str] = self._read_md()
        # 2. 解析 MD 表格 (Parse MD table)
        self._parse_md_table(lines)
        # 3. 检测循环依赖 (Detect cyclic dependencies)
        self._detect_cycles()
        # 4. 计算分层布局 (Calculate layered layout)
        layers: Dict[int, List[str]] = self._compute_layers()
        # 5. 计算节点位置 (Calculate node positions)
        positions: Dict[str, Tuple[float, float]] = self._layout_positions(layers)
        # 6. 生成 SVG (Generate SVG)
        svg: str = self._render_svg(positions)
        # 7. 组装 HTML (Assemble HTML)
        html_doc: str = self._assemble_html(
            svg, title=f"依赖可视化：{os.path.basename(self.md_path)}"
        )

        # 确保输出目录存在 (Ensure output directory exists)
        out_dir: str = os.path.dirname(out_html)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # 写入 HTML 文件 (Write to HTML file)
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(html_doc)

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    # 计算默认路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))
    default_root = os.path.join(repo_root, "firmware")
    default_output = os.path.join(repo_root, "build", "dependencies.md")

    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="""分析指定目录下 Python 文件的依赖关系，并生成可视化报告。

        该工具会递归扫描指定目录下的所有 Python 文件，分析模块间的依赖关系，
        生成 Markdown 格式的依赖报告，还可以进一步生成交互式 HTML 可视化图表。
        支持通过命令行参数自定义输入目录、输出路径和运行模式。
        """,
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""使用示例:
          # 使用默认配置分析项目
          python dependency_analyzer.py
        
          # 分析指定目录并输出到自定义路径
          python dependency_analyzer.py ./my_project -o ./reports/deps.md
        
          # 静默模式运行并生成可视化
          python dependency_analyzer.py -q --visualize
        
          # 生成可视化到指定路径
          python dependency_analyzer.py -z ./viz/dependencies.html
        """
    )

    # 位置参数：项目根目录
    parser.add_argument(
        "root",
        nargs="?",
        default=default_root,
        help=f"""要分析的项目根目录（程序会递归扫描所有 .py 文件）。
                 默认值: {default_root}
        """
    )

    # 可选参数：输出文件路径
    parser.add_argument(
        "-o",
        "--output",
        help=f"""输出的 Markdown 报告文件路径。
        如果指定目录不存在，会自动创建。
        默认值: {default_output}
        """,
        default=default_output,
    )

    # 可选参数：静默模式
    parser.add_argument(
        "-q", "--quiet",
        help="静默模式运行，仅输出关键信息和错误提示",
        action="store_true"
    )

    # 可选参数：生成可视化
    parser.add_argument(
        "--visualize",
        "-z",
        nargs="?",
        const=True,
        help="""生成依赖关系的 HTML 可视化图表。
        如果不带参数，则默认在 Markdown 报告同目录生成 dependencies.html；
        如果指定路径，则输出到该路径。
        """
    )

    # 解析命令行参数
    args = parser.parse_args()

    # 验证输入目录是否存在
    if not os.path.isdir(args.root):
        print(f"错误：指定的目录 '{args.root}' 不存在或不是一个目录", file=sys.stderr)
        sys.exit(2)

    # 确保输出目录存在
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.exists(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            print(f"错误：无法创建输出目录 '{out_dir}'：{e}", file=sys.stderr)
            sys.exit(2)

    # 执行依赖分析
    try:
        analyzer = DependencyAnalyzer(
            root=args.root,
            out_md=args.output,
            verbose=not args.quiet
        )
        analyzer.run()

        # 输出报告生成信息
        md_out = os.path.abspath(args.output)
        print(f"✅ 依赖分析完成：报告已生成 -> {md_out}")

        # 处理可视化请求
        if args.visualize:
            # 确定可视化输出路径
            if args.visualize is True:
                # 使用默认路径（与MD报告同目录）
                out_html = os.path.splitext(md_out)[0] + ".html"
            else:
                # 使用用户指定的路径
                out_html = os.path.abspath(args.visualize)
                # 确保可视化输出目录存在
                viz_dir = os.path.dirname(out_html)
                if viz_dir and not os.path.exists(viz_dir):
                    os.makedirs(viz_dir, exist_ok=True)

            # 生成可视化HTML
            vis = MarkdownVisualizer(md_path=md_out)
            vis.generate_html(out_html)
            print(f"✅ 可视化完成：HTML已生成 -> {out_html}")

        sys.exit(0)

    except Exception as e:
        print(f"❌ 执行过程中发生错误：{str(e)}", file=sys.stderr)
        if not args.quiet:
            import traceback

            traceback.print_exc()
        sys.exit(1)