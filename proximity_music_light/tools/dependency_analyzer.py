# Python env   : Python 3.12.0 ()
# -*- coding: utf-8 -*-        
# @Time    : 2025/9/20 上午10:31   
# @Author  : 李清水            
# @File    : dependency_analyzer.py       
# @Description : 面向对象的 Python 文件依赖分析器。

import ast
import os
import sys
import argparse
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple, Callable
import re
import html
import math

# -----------------------------
# 数据类：表示文件节点和依赖信息
# -----------------------------
class FileNode:
    """
    表示一个 Python 文件（模块）及其依赖信息。
    - module_id: 相对路径（不含 .py），用 / 分隔，作为唯一标识
    - dotted_name: 如果是 package 路径则为点分名，否则与 module_id 用 . 替换 /（但可能不是有效包）
    - path: 文件系统绝对路径
    - imports_internal: 指向 root 内其他 module_id 的集合
    - imports_external: 未解析到 root 内的导入（第三方或标准库），集合 of str
    - imported_by: 被哪些 module_id 导入（填充在构建图后）
    """
    def __init__(self, module_id: str, path: str, dotted_name: Optional[str]):
        self.module_id = module_id
        self.path = path
        self.dotted_name = dotted_name or module_id.replace('/', '.')
        self.imports_internal: Set[str] = set()
        self.imports_external: Set[str] = set()
        self.imported_by: Set[str] = set()
        self.size_bytes: int = os.path.getsize(path) if os.path.exists(path) else 0

    def to_md_row(self) -> str:
        """
        生成 Markdown 表格中的一行（管道分隔）。
        - Imports 列列出内部依赖简短列表（最多显示 6 个），并说明数量。
        - Imported-by 列说明被谁引用（数量）。
        """
        def short_list(sset: Set[str], limit=6) -> str:
            if not sset:
                return "-"
            items = sorted(sset)
            if len(items) <= limit:
                return ", ".join(items)
            return ", ".join(items[:limit]) + f", ... ({len(items)} total)"
        imports_internal_s = short_list(self.imports_internal)
        imports_external_s = short_list(self.imports_external)
        imported_by_s = short_list(self.imported_by)
        # 保证单行不换行（表格显示）
        return f"| `{self.module_id}` | `{self.dotted_name}` | {self.size_bytes} | {imports_internal_s} | {imports_external_s} | {imported_by_s} |"

# -----------------------------
# 解析器与图构建器
# -----------------------------
class DependencyAnalyzer:
    """
    依赖分析器主类（面向对象）。
    使用方法：
      analyzer = DependencyAnalyzer(root_path)
      analyzer.run()  # 扫描、解析、构建、输出
    关键步骤：
      - scan_files: 收集 .py 文件
      - build_module_map: 构造 module_id -> path 映射与 dotted_name
      - parse_all_files: ast 解析导入语句并尝试解析成内部/外部依赖
      - link_reverse: 构建 imported_by 反向关系
      - find_cycles: 检测循环依赖
      - export_markdown: 输出 md 文件
    """
    def __init__(self, root: str, out_md: str = "dependencies.md", verbose: bool = True):
        self.root = os.path.abspath(root)                       # 根目录绝对路径
        self.out_md = out_md                                    # 输出 Markdown 文件路径
        self.verbose = verbose
        self.module_map: Dict[str, str] = {}                    # module_id -> absolute path
        self.dotted_map: Dict[str, str] = {}                    # module_id -> dotted_name
        self.nodes: Dict[str, FileNode] = {}                    # module_id -> FileNode

    # ---------- 扫描与模块标识 ----------
    def scan_files(self) -> None:
        """
        遍历 root 目录，收集所有 .py 文件（排除隐藏目录和 __pycache__）。
        对每个文件生成 module_id（相对路径，不含 .py）并加入 module_map。
        同时尝试生成 dotted_name（如果路径中各层都有 __init__.py）
        """
        if self.verbose:
            print(f"[scan] scanning {self.root} ...")
        root_len = len(self.root.rstrip(os.sep)) + 1
        for dirpath, dirnames, filenames in os.walk(self.root):
            # 排除 __pycache__ 等不需要的目录
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != "__pycache__"]
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                full = os.path.join(dirpath, fname)
                rel = full[root_len:]  # 相对路径（含文件名）
                # module_id 使用 unix 风格分隔符，不含 .py
                rel_noext = rel[:-3].replace(os.sep, '/')
                # 记录 module map
                self.module_map[rel_noext] = full
        if self.verbose:
            print(f"[scan] found {len(self.module_map)} python files")

    def _compute_dotted_name(self, rel_noext: str, abs_path: str) -> Optional[str]:
        """
        尝试为相对路径生成 dotted_name（仅当路径所有中间目录均存在 __init__.py 时）。
        返回 None 表示该路径不构成 package 树（仍可使用 module_id 作为标识）。
        """
        parts = rel_noext.split('/')
        # 对于 module 在子目录下的情况，检查每个父目录是否含 __init__.py
        cur = self.root
        dotted_parts = []
        for i, p in enumerate(parts[:-1]):  # 逐层检查目录是否为包
            cur = os.path.join(cur, p)
            init_f = os.path.join(cur, "__init__.py")
            if not os.path.exists(init_f):
                # 一旦某层没有 __init__.py，就不是完整的 package 树
                return None
            dotted_parts.append(p)
        # 最后一部分可能是模块名或包（模块名）
        dotted_parts.append(parts[-1])
        return ".".join(dotted_parts)

    def build_module_map(self) -> None:
        """
        用 scan_files 的结果构建 FileNode 实例：
        - module_id -> FileNode
        - dotted_map 同步
        """
        for module_id, abs_path in sorted(self.module_map.items()):
            dotted = self._compute_dotted_name(module_id, abs_path)
            node = FileNode(module_id=module_id, path=abs_path, dotted_name=dotted)
            self.nodes[module_id] = node
            self.dotted_map[module_id] = node.dotted_name

    # ---------- 解析 AST，收集导入 ----------
    def _parse_imports_from_ast(self, tree: ast.AST, cur_module_id: str) -> Tuple[Set[str], Set[str]]:
        """
        从 ast 树中提取导入：
        - 返回 (internal_targets, external_targets)
        internal_targets: 能解析到 root 内 module_id 的集合
        external_targets: 无法解析到 root 内的导入
        """
        internal: Set[str] = set()
        external: Set[str] = set()
        # 当前模块的 dotted 名称（可能是文件路径形式）
        cur_dotted = self.nodes[cur_module_id].dotted_name if cur_module_id in self.nodes else None

        for node in ast.walk(tree):
            # 处理 `import a.b as c`
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name  # 形如 pkg.sub.module 或 pkg
                    resolved = self._resolve_name_to_module(name)
                    if resolved:
                        internal.add(resolved)
                    else:
                        external.add(name)
            # 处理 `from x import y`，可能包含相对导入 level
            elif isinstance(node, ast.ImportFrom):
                module = node.module  # 形如 'pkg.sub' 或 None（when 'from . import x'）
                level = node.level    # 0 表示绝对导入，大于0 表示相对导入
                # 计算实际被导入的模块基名（可能是包或模块）
                base_candidates = []
                if level and level > 0:
                    # 相对导入，基于当前模块的 dotted_name 来解析
                    # 尝试把 dotted 名称转为 components
                    comps = cur_dotted.split('.') if cur_dotted else cur_module_id.split('/')
                    # 当模块是文件（a.b.c），基于当前模块去掉最后一段作为 package 基础
                    if len(comps) >= 1:
                        # 计算上溯层级
                        if level <= len(comps):
                            base = comps[:-level]
                        else:
                            base = []
                        if module:
                            base = base + module.split('.')
                        if base:
                            candidate = ".".join(base)
                        else:
                            candidate = module or ""
                        base_candidates.append(candidate)
                    else:
                        # 无法通过 dotted_name 解析，保守处理为外部
                        if module:
                            base_candidates.append(module)
                else:
                    # 绝对导入：直接尝试 module
                    if module:
                        base_candidates.append(module)
                    else:
                        # from . import x 这种特殊情况，level handled above
                        pass

                # 对于每个被 import 的 name（alias 可以是具体 symbol），我们尝试解析基名或基名加 symbol
                for alias in node.names:
                    alias_name = alias.name  # symbol 或子模块名
                    resolved_any = False
                    # 先尝试基候选
                    for base in base_candidates:
                        # try base + '.' + alias_name, then base
                        combos = []
                        if base:
                            combos.append(f"{base}.{alias_name}")
                            combos.append(base)
                        else:
                            combos.append(alias_name)
                        for combo in combos:
                            r = self._resolve_name_to_module(combo)
                            if r:
                                internal.add(r)
                                resolved_any = True
                                break
                        if resolved_any:
                            break
                    if not base_candidates:
                        # 没有 module 基础（例如 from . import x 在没有 dotted 名称时）
                        # 仅尝试 alias_name
                        r = self._resolve_name_to_module(alias_name)
                        if r:
                            internal.add(r)
                            resolved_any = True
                    if not resolved_any:
                        # 仍然无法解析到内部模块，记作外部导入（以模块形态记录）
                        # 使用最具信息性的字符串：若 module 存在则 module.alias，否则 alias
                        if module:
                            external.add(f"{module}.{alias_name}")
                        else:
                            external.add(alias_name)
        return internal, external

    def _resolve_name_to_module(self, fullname: str) -> Optional[str]:
        """
        将一个导入名（例如 'pkg.sub.mod' 或 'pkg'）解析为 root 内的 module_id（rel path），
        尝试以下匹配：
          - fullname -> check file fullname.py 或 package dirname/fullname/__init__.py
          - 逐层向上截断（例如导入 pkg.sub.mod，但只有 pkg/sub/__init__.py 存在）
        返回匹配到的 module_id（使用 / 分隔），或 None（表示外部/未找到）
        """
        if not fullname:
            return None
        parts = fullname.split('.')
        # 生成优先的匹配候选（越具体越优先）
        candidates = []
        for cut in range(len(parts), 0, -1):
            left = parts[:cut]  # e.g. ['pkg','sub','mod']
            rel_path = "/".join(left)
            # 两种可能：rel_path.py 或 rel_path/__init__.py
            candidates.append(rel_path)
        # 尝试候选是否在 module_map keys
        for cand in candidates:
            if cand in self.module_map:
                return cand
            # 有时包作为目录结构存在：cand might be a package name and module we want is cand/__init__
            # 但 module_map keys were recorded without trailing /__init__.py; our scanning stored file paths per rel_noext
            # example: package 'pkg/sub' corresponds to module_id 'pkg/sub/__init__'? No — we recorded module_id 'pkg/sub/__init__' only if file is named '__init__.py'
            # So cand equal to 'pkg/sub' will only match if there is pkg/sub.py.
            # To match package __init__.py we need to check candidate + '/__init__'? However our module_id uses rel path without .py; __init__.py was added as 'pkg/sub/__init__' in module_map.
            # So also try cand + '/__init__'
            alt = cand + "/__init__"
            if alt in self.module_map:
                return alt
        return None

    def parse_all_files(self) -> None:
        """
        对每个文件执行 ast.parse，并收集内部/外部依赖。
        解析失败的文件会被跳过（并在 verbose 模式下报告）。
        """
        if self.verbose:
            print("[parse] parsing files and resolving imports ...")
        for module_id, node in self.nodes.items():
            try:
                with open(node.path, 'r', encoding='utf-8') as f:
                    src = f.read()
                tree = ast.parse(src, filename=node.path)
            except Exception as e:
                if self.verbose:
                    print(f"[parse] failed to parse {node.path}: {e}")
                continue
            internal, external = self._parse_imports_from_ast(tree, module_id)
            node.imports_internal = internal
            node.imports_external = external

    # ---------- 反向链接与循环检测 ----------
    def link_reverse(self) -> None:
        """
        使用 nodes 中的 imports_internal，构建每个节点的 imported_by 列表（反向依赖）。
        """
        # 清空 imported_by
        for node in self.nodes.values():
            node.imported_by = set()
        # 构造反向关系
        for module_id, node in self.nodes.items():
            for tgt in node.imports_internal:
                if tgt in self.nodes:
                    self.nodes[tgt].imported_by.add(module_id)

    def find_cycles(self) -> List[List[str]]:
        """
        使用 DFS 检测循环依赖，返回所有发现的 cycle（每个 cycle 为 module_id 列表）。
        基本算法：对有向图做回溯 DFS，发现回边记录路径。
        """
        if self.verbose:
            print("[cycles] detecting cycles ...")
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {m: WHITE for m in self.nodes}
        parent = {}
        cycles = []

        def dfs(u):
            color[u] = GRAY
            for v in self.nodes[u].imports_internal:
                if v not in self.nodes:
                    continue
                if color[v] == WHITE:
                    parent[v] = u
                    dfs(v)
                elif color[v] == GRAY:
                    # 找到回边 v <- ... <- u，构造 cycle
                    cycle = [v]
                    cur = u
                    while cur != v and cur in parent:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(v)
                    cycle.reverse()
                    # 去重：只保留新 cycle（以字符串形式判断）
                    key = "->".join(cycle)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cycle)
            color[u] = BLACK

        seen_cycles = set()
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
        生成 Markdown 文件：
          - 总览（文件数、cycles 等）
          - 表格：Module | Dotted | Size | Imports(internal) | Imports(external) | Imported-by
          - 如果有 cycle，则列出详细 cycle
        """
        if self.verbose:
            print(f"[export] writing markdown to {self.out_md}")
        lines = []
        lines.append("# Python 文件依赖分析报告\n")
        lines.append(f"- 根目录：`{self.root}`  \n")
        lines.append(f"- 文件数量：**{len(self.nodes)}**  \n")
        if cycles:
            lines.append(f"- 检测到循环依赖：**{len(cycles)}** 个（见下方）  \n")
        else:
            lines.append(f"- 检测到循环依赖：**0**  \n")
        lines.append("\n---\n")
        lines.append("## 模块依赖表\n")
        lines.append("（`module_id` 使用相对路径作为唯一标识；`dotted_name` 如果为包路径则为点分名）\n")
        lines.append("\n| Module (module_id) | Dotted name | Size (bytes) | Imports (internal) | Imports (external) | Imported-by |\n")
        lines.append("|---|---:|---:|---|---|---|\n")
        for module_id in sorted(self.nodes):
            row = self.nodes[module_id].to_md_row()
            lines.append(row + "\n")
        # cycles 详细
        if cycles:
            lines.append("\n---\n")
            lines.append("## 循环依赖详情\n")
            for i, cyc in enumerate(cycles, 1):
                lines.append(f"- Cycle {i}: `{' -> '.join(cyc)}`  \n")
        # 额外：按被引用次数排序的 TopN
        lines.append("\n---\n")
        lines.append("## 被引用次数排行（Top 20）\n")
        counts = sorted(((m, len(n.imported_by)) for m, n in self.nodes.items()), key=lambda x: -x[1])
        lines.append("| Module | Imported-by count |\n")
        lines.append("|---|---:|\n")
        for m, c in counts[:20]:
            lines.append(f"| `{m}` | {c} |\n")
        # 写文件
        with open(self.out_md, 'w', encoding='utf-8') as f:
            f.writelines(line if line.endswith("\n") else line + "\n" for line in lines)
        if self.verbose:
            print("[export] done.")

    # ---------- 一键运行接口 ----------
    def run(self) -> None:
        """
        一键运行流程：
          scan_files -> build_module_map -> parse_all_files -> link_reverse -> find_cycles -> export_markdown
        """
        self.scan_files()
        self.build_module_map()
        self.parse_all_files()
        self.link_reverse()
        cycles = self.find_cycles()
        self.export_markdown(cycles)


class MarkdownVisualizer:
    """
    更健壮的 Markdown -> HTML 可视化生成器。
    修复点：
      - 使用按照 '|' 列拆分的解析方式，兼容更多表格样式。
      - 同时利用 Imports(internal) 和 Imported-by 列来推断完整边，避免单侧截断导致的缺边。
      - 仍然使用纯标准库，不依赖第三方。
    新增功能：
      - 模块分组视觉标识：通过颜色区分引导核心、板级配置、任务层、驱动层、公共库。
    使用：
      vis = MarkdownVisualizer(md_path="build/dependencies.md")
      vis.generate_html("build/dependencies.html")
    """
    # 节点尺寸
    NODE_WIDTH = 300
    NODE_HEIGHT = 40
    LAYER_V_SPACING = 300  # 增加层间距，给箭头更多空间
    NODE_H_SPACING = 150  # 增加节点水平间距
    MARGIN = 30
    # 箭头参数
    ARROW_OFFSET = 0  # 增大箭头与节点的距离
    ARROW_SPACING = 20  # 多个箭头之间的间距

    # 模块分组配置（分组名 → (匹配函数, 边框色, 背景色)）
    GROUP_CONFIG: Dict[str, Tuple[Callable[[str], bool], str, str]] = {
        "引导核心": (
            lambda mid: mid in ("boot", "main"),  # 精确匹配核心入口文件
            "#2563eb",  # 蓝色边框
            "#eff6ff"  # 浅蓝色背景
        ),
        "板级配置": (
            lambda mid: mid in ("board", "conf"),  # 精确匹配配置文件
            "#7c3aed",  # 紫色边框
            "#f5f3ff"  # 浅紫色背景
        ),
        "任务层": (
            lambda mid: mid.startswith("tasks/"),  # 匹配 tasks/ 目录下的文件
            "#16a34a",  # 绿色边框
            "#ecfdf5"  # 浅绿色背景
        ),
        "驱动层": (
            lambda mid: mid.startswith("drivers/"),  # 匹配 drivers/ 目录下的文件
            "#ea580c",  # 橙色边框
            "#fff7ed"  # 浅橙色背景
        ),
        "公共库": (
            lambda mid: mid.startswith("libs/"),  # 匹配 libs/ 目录下的文件
            "#0891b2",  # 青色边框
            "#ecfeff"  # 浅青色背景
        )
    }

    # 用于跟踪同一对节点间的箭头数量，解决重叠问题
    edge_counter: Dict[Tuple[str, str], int] = {}

    def __init__(self, md_path: str):
        self.md_path = md_path
        self.nodes: Dict[str, Dict] = {}  # module_id -> { dotted, imports(set), external(set), imported_by(set) }
        self.adj: Dict[str, Set[str]] = {}  # adjacency list u -> set(v)
        self.cycles: List[List[str]] = []
        self._canvas_w = 800
        self._canvas_h = 600

    # ---------------- MD 解析部分 ----------------
    def _read_md(self) -> List[str]:
        with open(self.md_path, 'r', encoding='utf-8') as f:
            return f.readlines()

    def _clean_item(self, s: str) -> str:
        s = s.strip()
        if s.startswith('`') and s.endswith('`'):
            s = s[1:-1].strip()
        s = re.sub(r',\s*\.\.\..*$', '', s)
        return s

    def _split_cell(self, cell: str) -> List[str]:
        cell = cell.strip()
        if cell in ("", "-"):
            return []
        cell = cell.replace('`', '')
        cell = re.sub(r',\s*\.\.\..*$', '', cell)
        parts = [p.strip() for p in cell.split(',') if p.strip()]
        return parts

    def _parse_md_table(self, lines: List[str]) -> None:
        in_table = False
        for i, ln in enumerate(lines):
            ln = ln.rstrip('\n')
            if not in_table:
                if ln.strip().startswith("|") and re.search(r'\|\s*-{3,}', ln):
                    in_table = True
                continue
            if not ln.strip().startswith("|"):
                break
            cols = ln.split('|')[1:-1]
            cols = [c.strip() for c in cols]
            if len(cols) < 6:
                continue
            module_col = cols[0]
            dotted_col = cols[1]
            size_col = cols[2]
            imports_internal_col = cols[3]
            imports_external_col = cols[4]
            imported_by_col = cols[5]

            module_id = self._clean_item(module_col)
            dotted = self._clean_item(dotted_col)
            imports_internal = self._split_cell(imports_internal_col)
            imports_external = self._split_cell(imports_external_col)
            imported_by = self._split_cell(imported_by_col)

            self.nodes[module_id] = {
                'dotted': dotted,
                'imports': set(imports_internal),
                'external': set(imports_external),
                'imported_by': set(imported_by)
            }

        for m in self.nodes:
            self.adj[m] = set()

        for u, v in self.nodes.items():
            for tgt in v['imports']:
                if tgt in self.nodes:
                    self.adj[u].add(tgt)

        for node, v in self.nodes.items():
            for importer in v['imported_by']:
                if importer in self.nodes:
                    self.adj[importer].add(node)

    # ---------------- 布局与 cycle 检测部分 ----------------
    def _compute_layers(self) -> Dict[int, List[str]]:
        indeg = {u: 0 for u in self.adj}
        for u, vs in self.adj.items():
            for v in vs:
                indeg[v] = indeg.get(v, 0) + 1

        layers: Dict[int, List[str]] = {}
        q = [u for u, d in indeg.items() if d == 0]
        placed = set()
        layer_idx = 0
        while q:
            layers[layer_idx] = sorted(q)
            placed.update(q)
            next_q = []
            for u in q:
                for v in self.adj.get(u, []):
                    indeg[v] -= 1
                    if indeg[v] == 0:
                        next_q.append(v)
            q = sorted(set(next_q))
            layer_idx += 1
        remaining = [u for u in self.adj if u not in placed]
        if remaining:
            layers[layer_idx] = sorted(remaining)
        return layers

    def _layout_positions(self, layers: Dict[int, List[str]]) -> Dict[str, Tuple[float, float]]:
        positions: Dict[str, Tuple[float, float]] = {}
        max_width = 0
        total_height = self.MARGIN * 2
        for li, nodes in layers.items():
            layer_h = self.NODE_HEIGHT
            total_height += layer_h
            if li > 0:
                total_height += self.LAYER_V_SPACING
            width = len(nodes) * self.NODE_WIDTH + max(0, len(nodes) - 1) * self.NODE_H_SPACING
            if width > max_width:
                max_width = width
        canvas_w = max(300, max_width + self.MARGIN * 2)
        y = self.MARGIN
        for li in sorted(layers):
            nodes = layers[li]
            layer_w = len(nodes) * self.NODE_WIDTH + max(0, len(nodes) - 1) * self.NODE_H_SPACING
            x0 = (canvas_w - layer_w) / 2 + self.NODE_WIDTH / 2
            for i, m in enumerate(nodes):
                cx = x0 + i * (self.NODE_WIDTH + self.NODE_H_SPACING)
                cy = y + self.NODE_HEIGHT / 2
                positions[m] = (cx, cy)
            y += self.NODE_HEIGHT + self.LAYER_V_SPACING
        self._canvas_w = math.ceil(canvas_w)
        self._canvas_h = math.ceil(y + self.MARGIN)
        return positions

    def _escape(self, s: str) -> str:
        return html.escape(s)

    def _detect_cycles(self) -> None:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self.adj}
        parent = {}
        cycles = []
        seen = set()

        def dfs(u):
            color[u] = GRAY
            for v in self.adj.get(u, []):
                if v not in color:
                    continue
                if color[v] == WHITE:
                    parent[v] = u
                    dfs(v)
                elif color[v] == GRAY:
                    cur = u
                    path = [v]
                    while cur != v and cur in parent:
                        path.append(cur)
                        cur = parent[cur]
                    path.append(v)
                    path.reverse()
                    key = "->".join(path)
                    if key not in seen:
                        seen.add(key)
                        cycles.append(path)
            color[u] = BLACK

        for n in list(self.adj.keys()):
            if color[n] == WHITE:
                parent[n] = None
                dfs(n)
        self.cycles = cycles

    # ---------------- 新增：分组样式匹配方法 ----------------
    def _get_group_style(self, module_id: str) -> Tuple[str, str]:
        """根据模块ID匹配分组，返回 (边框色, 背景色)，无匹配则返回默认值"""
        print(f"[分组匹配调试] 模块ID: {module_id}")
        for name, (match_func, border_color, bg_color) in self.GROUP_CONFIG.items():
            if match_func(module_id):
                print(f"[分组匹配调试] 匹配到分组: {name}")
                return (border_color, bg_color)
        print(f"[分组匹配调试] 未匹配到任何分组")
        # 默认样式（非分组模块）
        return ("#333", "#ffffff")

    # ---------------- SVG 渲染部分 ----------------
    def _render_svg(self, positions: Dict[str, Tuple[float, float]]) -> str:
        svg_items: List[str] = []
        # 重置箭头计数器
        self.edge_counter = {}

        # 定义箭头标记
        svg_items.append(f'''<defs>
            <marker id="arrow" markerWidth="18" markerHeight="18" refX="16" refY="9" orient="auto">
                <path d="M0,0 L18,9 L0,18 z" fill="#555" />
            </marker>
        </defs>''')

        # 绘制依赖边
        for u, vs in self.adj.items():
            if u not in positions:
                continue
            ux, uy = positions[u]

            # 对目标节点排序，确保箭头顺序一致
            sorted_vs = sorted(vs)
            for v in sorted_vs:
                if v not in positions:
                    continue
                vx, vy = positions[v]

                # 跟踪同一对节点的箭头数量，计算偏移量
                edge_key = (u, v)
                self.edge_counter[edge_key] = self.edge_counter.get(edge_key, 0) + 1
                edge_index = self.edge_counter[edge_key] - 1

                # 多箭头时分散排列
                offset = 0
                if self.edge_counter[edge_key] > 1:
                    mid = (self.edge_counter[edge_key] - 1) / 2
                    offset = (edge_index - mid) * self.ARROW_SPACING

                # 计算箭头起点（远离源节点）
                if vx > ux + self.NODE_WIDTH / 4:  # 目标在右侧
                    start_x = ux + self.NODE_WIDTH / 2 - self.ARROW_OFFSET
                    start_y = uy + offset
                elif vx < ux - self.NODE_WIDTH / 4:  # 目标在左侧
                    start_x = ux - self.NODE_WIDTH / 2 + self.ARROW_OFFSET
                    start_y = uy + offset
                elif vy > uy:  # 目标在下方
                    start_x = ux + offset
                    start_y = uy + self.NODE_HEIGHT / 2 - self.ARROW_OFFSET
                else:  # 目标在上方
                    start_x = ux + offset
                    start_y = uy - self.NODE_HEIGHT / 2 + self.ARROW_OFFSET

                # 计算箭头终点（远离目标节点）
                if vx > ux + self.NODE_WIDTH / 4:  # 从右侧进入
                    end_x = vx - self.NODE_WIDTH / 2 + self.ARROW_OFFSET
                    end_y = vy + offset
                elif vx < ux - self.NODE_WIDTH / 4:  # 从左侧进入
                    end_x = vx + self.NODE_WIDTH / 2 - self.ARROW_OFFSET
                    end_y = vy + offset
                elif vy > uy:  # 从上方进入
                    end_x = vx + offset
                    end_y = vy - self.NODE_HEIGHT / 2 + self.ARROW_OFFSET
                else:  # 从下方进入
                    end_x = vx + offset
                    end_y = vy + self.NODE_HEIGHT / 2 - self.ARROW_OFFSET

                # 计算贝塞尔曲线控制点，使路径自然
                dx = end_x - start_x
                dy = end_y - start_y
                if abs(dx) > abs(dy):  # 水平为主
                    curve_factor = 0.4 if abs(dx) > 100 else 0.6
                    cx1 = start_x + dx * curve_factor
                    cy1 = start_y + dy * 0.1
                    cx2 = end_x - dx * curve_factor
                    cy2 = end_y - dy * 0.1
                else:  # 垂直为主
                    curve_factor = 0.4 if abs(dy) > 100 else 0.6
                    cx1 = start_x + dx * 0.1
                    cy1 = start_y + dy * curve_factor
                    cx2 = end_x - dx * 0.1
                    cy2 = end_y - dy * curve_factor

                # 绘制曲线箭头
                path = f'M {start_x:.1f},{start_y:.1f} C {cx1:.1f},{cy1:.1f} {cx2:.1f},{cy2:.1f} {end_x:.1f},{end_y:.1f}'
                svg_items.append(
                    f'<path d="{path}" fill="none" stroke="#555" stroke-width="2.0" marker-end="url(#arrow)" />')

        # 绘制节点（应用分组样式）
        cycle_nodes = set()
        for cyc in self.cycles:
            cycle_nodes.update(cyc)

        for m, pos in positions.items():
            cx, cy = pos
            x = cx - self.NODE_WIDTH / 2
            y = cy - self.NODE_HEIGHT / 2
            is_cycle = m in cycle_nodes

            # 样式优先级：循环依赖 > 分组样式 > 默认样式
            if is_cycle:
                fill = "#ffecec"
                stroke = "#c33"
            else:
                stroke, fill = self._get_group_style(m)

            # 绘制节点矩形和文本
            svg_items.append(f'<g class="node" data-id="{self._escape(m)}">')
            svg_items.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{self.NODE_WIDTH}" height="{self.NODE_HEIGHT}" rx="6" ry="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5" />')
            display = m if len(m) <= 50 else (m[:46] + "...")
            svg_items.append(
                f'<text x="{(cx - self.NODE_WIDTH / 2) + 10:.1f}" y="{cy + 7:.1f}" font-family="sans-serif" font-size="14">{self._escape(display)}</text>')
            svg_items.append('</g>')

        # 组装SVG
        svg_body = "\n".join(svg_items)
        svg = f'<svg width="{self._canvas_w}" height="{self._canvas_h}" viewBox="0 0 {self._canvas_w} {self._canvas_h}" xmlns="http://www.w3.org/2000/svg" role="img">\n{svg_body}\n</svg>'
        return svg

    # ---------------- HTML 组装部分 ----------------
    def _assemble_html(self, svg: str, title: str) -> str:
        # 循环依赖提示
        cycle_note = ""
        if self.cycles:
            cycle_note = f'<p style="color:#a33">注意：检测到 {len(self.cycles)} 个循环依赖（部分节点）。循环节点用红色标注。</p>'

        # 分组图例
        group_legend = """
        <div class="group-legend" style="margin: 12px 0; padding: 8px; background: #f0f0f0; border-radius: 4px;">
          <p style="margin: 0 0 8px 0; font-weight: bold;">模块分组说明：</p>
          <ul style="margin: 0; padding-left: 20px; line-height: 1.6;">
            <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #2563eb; background: #eff6ff;"></span>引导核心：boot、main.py</li>
            <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #7c3aed; background: #f5f3ff;"></span>板级配置：board、conf</li>
            <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #16a34a; background: #ecfdf5;"></span>任务层：tasks/ 下所有任务文件</li>
            <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #ea580c; background: #fff7ed;"></span>驱动层：drivers/ 下所有驱动包</li>
            <li><span style="display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 1px solid #0891b2; background: #ecfeff;"></span>公共库：libs/ 下所有工具库（logger/network 等）</li>
          </ul>
        </div>
        """

        # 组装完整HTML
        html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial; padding: 16px; }}
    .svg-wrap {{ border: 1px solid #ddd; overflow: auto; padding: 16px; background: #fafafa; }}
    .legend {{ margin-top: 12px; font-size: 14px; color: #444; }}
    .group-legend {{ font-size: 14px; color: #444; }}
  </style>
</head>
<body>
  <h2>{html.escape(title)}</h2>
  {cycle_note}
  {group_legend}
  <div class="svg-wrap">{svg}</div>
  <div class="legend">
    <p><strong>说明：</strong>节点表示 module_id（相对路径或规范化名），箭头从模块指向其内部依赖。环路节点用红色背景。</p>
  </div>
</body>
</html>"""
        return html_doc

    # ---------------- 对外 API ----------------
    def generate_html(self, out_html: str) -> None:
        """生成依赖可视化HTML文件"""
        lines = self._read_md()
        self._parse_md_table(lines)
        self._detect_cycles()
        layers = self._compute_layers()
        positions = self._layout_positions(layers)
        svg = self._render_svg(positions)
        html_doc = self._assemble_html(svg, title=f"依赖可视化：{os.path.basename(out_html)}")

        # 确保输出目录存在
        out_dir = os.path.dirname(out_html)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # 写入HTML文件
        with open(out_html, 'w', encoding='utf-8') as f:
            f.write(html_doc)

# -----------------------------
# 命令行接口
# -----------------------------
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))
    default_root = os.path.join(repo_root, "firmware")
    default_output = os.path.join(repo_root, "build", "dependencies.md")

    parser = argparse.ArgumentParser(
        description="分析指定目录下 Python 文件的依赖关系，并生成 Markdown 报告。"
    )
    parser.add_argument("root", nargs="?", default=default_root,
                        help=f"要分析的项目根目录（递归扫描 .py 文件）。默认：{default_root}")
    parser.add_argument("-o", "--output", help=f"输出 Markdown 文件路径，默认 {default_output}",
                        default=default_output)
    parser.add_argument("-q", "--quiet", help="静默模式（减少输出）", action="store_true")
    parser.add_argument("--visualize", "-z", nargs="?", const=True,
                        help="可选：生成 HTML 可视化。若带路径则使用该路径，否则在 md 同目录生成 dependencies.html")
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"错误：{args.root} 不是一个目录")
        sys.exit(2)

    # 确保输出目录存在
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    analyzer = DependencyAnalyzer(root=args.root, out_md=args.output, verbose=not args.quiet)
    analyzer.run()
    md_out = os.path.abspath(args.output)
    print(f"完成：报告已生成 -> {md_out}")

    # 可视化（可选）
    if args.visualize:
        if args.visualize is True:
            out_html = os.path.splitext(md_out)[0] + ".html"
        else:
            out_html = os.path.abspath(args.visualize)
        vis = MarkdownVisualizer(md_path=md_out)
        vis.generate_html(out_html)
        print(f"可视化已生成 -> {out_html}")

if __name__ == "__main__":
    main()