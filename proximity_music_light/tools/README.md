# MicroPython 构建与部署工具使用指南

本项目提供了一套基于 `mpy_cross` 与 `mpremote` 的自动化工具链，用于：

* 依赖分析
* `.py` → `.mpy` 文件编译
* `.mpy` 文件批量上传至设备
* 设备文件管理

---

## 📦 环境准备

### 1. 安装依赖工具

在使用前，请确保系统已安装 Python 3.8+，然后运行：

```bash
pip install mpy_cross mpremote
```

> **说明：**
>
> * `mpy_cross`：用于将 Python 源码编译为 MicroPython `.mpy` 文件。
> * `mpremote`：用于与 MicroPython 设备交互（上传、下载、执行命令等）。

---

## 🧩 依赖分析

使用内置脚本分析 Python 模块依赖关系。

```bash
python tools/dependency_analyzer.py -o build/dependencies.md --visualize build/dependencies.html
```

**参数说明：**

| 参数            | 说明                    |
| ------------- | --------------------- |
| `-o`          | 输出依赖分析结果（Markdown 文件） |
| `--visualize` | 生成依赖图（HTML 格式）        |

执行后将在 `build/` 目录下生成：

* `dependencies.md`：文本化依赖分析报告
* `dependencies.html`：可视化依赖关系图（可用浏览器打开）

---

## ⚙️ 编译 `.mpy` 文件

顺序编译指定目录下的 Python 源文件：

```bash
python tools/mpy_compiler.py -s firmware -o build/firmware_mpy -vv
```

**参数说明：**

| 参数    | 说明                    |
| ----- | --------------------- |
| `-s`  | 源代码目录（例如 `firmware/`） |
| `-o`  | 输出目录（存放 `.mpy` 文件）    |
| `-vv` | 输出详细编译日志（可选）          |

**执行结果：**

* 所有 `.py` 文件将被依次编译为 `.mpy`
* 编译结果存放在 `build/firmware_mpy/` 目录下

---

## 📤 批量上传 `.mpy` 文件

将编译好的 `.mpy` 文件一次性上传到 MicroPython 设备：

```bash
python tools/mpy_uploader.py -s build/firmware_mpy -a
```

**参数说明：**

| 参数   | 说明                    |
| ---- | --------------------- |
| `-s` | 本地 `.mpy` 文件所在目录      |
| `-a` | 启用自动模式（自动检测设备并上传全部文件） |

> ⚠️ 上传前请确保设备已通过 USB 连接，并能被 `mpremote` 正常识别。

---

## 📋 查看设备文件

列出设备中当前存在的 `.mpy` 文件：

```bash
python tools/mpy_uploader.py -l
```

**输出示例：**

```
Connected to /dev/ttyACM0
Listing files in device root...
- main.py
- utils/config.mpy
- drivers/sensor.mpy
```

---

## 🔁 工作流程总结

1. **安装依赖**
   `pip install mpy_cross mpremote`

2. **分析依赖**
   `python tools/dependency_analyzer.py -o build/dependencies.md --visualize build/dependencies.html`

3. **编译源文件**
   `python tools/mpy_compiler.py -s firmware -o build/firmware_mpy -vv`

4. **上传至设备**
   `python tools/mpy_uploader.py -s build/firmware_mpy -a`

5. **验证设备内容**
   `python tools/mpy_uploader.py -l`

---

## 🧠 常见问题（FAQ）

**Q1：上传时报错 “Device not found”？**
请确认：

* 设备已连接并能被 `mpremote` 识别：

  ```bash
  mpremote connect list
  ```
* 若未列出，请检查 USB 权限或驱动。

**Q2：某些 `.py` 无法编译？**

* 检查是否使用了 MicroPython 不支持的标准库。
* 可手动测试单文件编译：

  ```bash
  mpy-cross your_module.py
  ```

**Q3：设备空间不足？**

* 可在上传前运行：

  ```bash
  mpremote fs ls
  ```

  并删除不必要的旧文件。

---

## 🧰 文件结构示例

```
project_root/
├── firmware/
│   ├── main.py
│   ├── utils/
│   │   └── helper.py
│   └── drivers/
│       └── sensor.py
├── tools/
│   ├── dependency_analyzer.py
│   ├── mpy_compiler.py
│   └── mpy_uploader.py
└── build/
    ├── dependencies.md
    ├── dependencies.html
    └── firmware_mpy/
        ├── main.mpy
        ├── utils/
        └── drivers/
```
