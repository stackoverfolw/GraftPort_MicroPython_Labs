# 智能植物健康监测与浇水提醒设备固件

## 目录
- [简介（Description）](#简介description)
- [主要功能（Features）](#主要功能features)
- [硬件要求（Hardware Requirements）](#硬件要求hardware-requirements)
- [软件环境（Software Environment）](#软件环境software-environment)
- [文件结构（File Structure）](#文件结构file-structure)
- [文件说明（File Description）](#文件说明file-description)
- [软件设计核心思想（Design Idea）](#软件设计核心思想design-idea)
- [使用说明（Quick Start）](#使用说明quick-start)
- [示例程序（Example）](#示例程序example)
- [注意事项（Notes）](#注意事项notes)
- [版本记录（Version History）](#版本记录version-history)
- [联系开发者（Contact）](#联系开发者contact)
- [许可协议（License）](#许可协议license)

## 简介（Description）
### 项目背景
传统植物养护依赖人工经验判断土壤湿度，存在浇水不及时或过量的问题，且缺乏直观的状态反馈机制。本项目基于GraftPort-RP2040开发板，整合土壤湿度传感器、OLED显示、蜂鸣器报警等模块，实现“湿度采集-阈值判断-智能提醒”的自动化流程，解决传统养护方式的主观性与滞后性问题。同时融入MicroPython轻量化任务调度与异常处理机制，确保系统在嵌入式环境下稳定可靠运行。

### 项目主要功能概览
本项目基于MicroPython开发，核心功能是通过土壤湿度传感器实时采集土壤水分数据，经滤波处理后与可调节阈值（通过滑动变阻器手动设置）对比；当湿度低于阈值时，触发蜂鸣器报警与LED闪烁提示，同时在OLED屏幕上显示当前湿度、阈值及报警状态；支持板载按键中断控制任务启停与传感器校准，内置自动垃圾回收（GC）避免内存泄漏，异常捕获机制便于问题定位。

### 适用场景或应用领域
- 家庭园艺：为盆栽植物提供精准浇水提醒，避免因遗忘或误判导致植物枯萎；  
- 智能温室：作为小型监测节点，实时反馈特定区域土壤湿度状态；  
- 教学演示：用于MicroPython传感器交互、PWM控制、OLED显示、任务调度等知识点的实践教学；  
- 创客项目：作为轻量化环境监测模块，快速集成到智能农业DIY作品中。

## 主要功能（Features）
- **实时湿度采集与滤波**：土壤湿度传感器每500ms采集一次数据，采用“五点均值滤波”机制，过滤瞬时干扰，保证数据稳定性；  
- **阈值灵活调节**：通过滑动变阻器手动设置湿度报警阈值，支持0-100%范围自定义，适配不同植物的生长需求；  
- **多方式报警提醒**：湿度低于阈值时，无源蜂鸣器发出间歇报警声，Piranha LED同步闪烁，同时OLED屏幕显示报警标识，多维度反馈状态；  
- **按键中断交互**：板载按键触发下降沿中断，短按切换任务“运行/暂停”，长按2秒进入传感器校准模式，操作直观高效；  
- **可视化数据展示**：SSD1306 OLED屏幕实时显示当前土壤湿度值、设定阈值及系统状态（运行/暂停/校准），信息一目了然；  
- **自动内存管理**：系统空闲时检测内存，若低于阈值（默认100000字节）自动触发GC，防止MicroPython因内存碎片导致运行异常；  
- **多板级适配**：基于board.py实现引脚映射解耦，支持后续扩展其他RP2040开发板，核心业务逻辑无需修改。

## 硬件要求（Hardware Requirements）

**其余需要的模块包括：**
- 土壤湿度传感器模块（模拟信号输出，接入ADC引脚）；  
- 滑动变阻器模块（用于阈值调节，接入ADC引脚）；  
- SSD1306 OLED显示屏模块（I2C通信，128x64分辨率，默认地址0x3C）；  
- 无源蜂鸣器模块（需PWM频率驱动，不支持直接高低电平控制）；  
- Piranha LED灯模块（单路LED，共阴极配置）；  
- 板载按键：默认使用开发板固定引脚（上拉输入），无需额外接线；  
- 供电模块：SY7656锂电池充放电模块（输出3.3V，为主控及各模块供电）。

**连接方式：**
1. **硬件连线**  
   - 土壤湿度传感器：VCC接3.3V、GND接GND、OUT接ADC引脚（参考board.py配置）；  
   - 滑动变阻器：VCC接3.3V、GND接GND、OUT接ADC引脚；  
   - OLED显示屏：VCC接3.3V、GND接GND、SDA接I2C-SDA引脚、SCL接I2C-SCL引脚；  
   - 无源蜂鸣器：VCC接3.3V、GND接GND、IN接PWM输出引脚；  
   - Piranha LED：VCC接3.3V、GND接GND、控制端接GPIO引脚（支持PWM调光）。

## 软件环境（Software Environment）
- 核心固件：MicroPython v1.23.0（需适配GraftPort-RP2040，支持`machine.Pin/I2C/ADC/PWM`模块、软定时器调度）；  
- 开发IDE：PyCharm（安装MicroPython插件，支持代码编写、上传、REPL调试交互）；  
- 辅助工具：  
  - Python 3.12+（可选，用于运行固件烧录、调试辅助脚本）；  
  - mpremote v0.11.0+（可选，替代Thonny实现命令行式文件上传与调试）；  
- 依赖模块：无额外第三方库，所有驱动（如SSD1306、蜂鸣器等）均为项目自定义实现，随文件提供。

## 文件结构（File Structure）
```
firmware/
├── boot.py            # 启动脚本，初始化板载 LED，为系统启动做准备
├── main.py            # 项目入口文件，负责硬件初始化、任务创建与调度启动
├── board.py           # 板级支持文件，定义 GraftPort-RP2040 的引脚映射
├── conf.py            # 配置文件，存放可自定义参数（GC 阈值、调试开关等）
├── drivers/           # 硬件驱动文件夹，封装各外设的控制接口
│   ├── passive_buzzer_driver/  # 无源蜂鸣器驱动，提供play_tone()方法
│   ├── piranha_led_driver/     # Piranha LED 驱动，提供set_brightness()方法
│   ├── potentiometer_driver/   # 滑动变阻器驱动，提供read_value()方法
│   ├── soil_moisture_driver/   # 土壤湿度传感器驱动，提供read_humidity()方法
│   └── ssd1306_driver/         # SSD1306 OLED 驱动，提供display_data()方法
├── libs/              # 通用工具库文件夹
│   └── scheduler.py   # 任务调度器库，实现多任务周期管理、空闲 / 异常回调
└── tasks/             # 任务逻辑文件夹，与硬件驱动解耦
    ├── maintenance.py # 维护任务模块，提供自动 GC、异常处理函数
    └── sensor_task.py # 核心任务模块，定义SoilMonitorTask类，实现监测逻辑

```

## 文件说明（File Description）
- `main.py`：项目入口，核心逻辑包括：  
  1. 上电延时3秒等待硬件稳定，通过board.py初始化各模块引脚（OLED、蜂鸣器、LED、按键等）；  
  2. 初始化I2C总线与OLED显示屏、各传感器模块，支持多次重试，失败则调用`fatal_hang`阻塞并闪灯报错；  
  3. 创建`SoilMonitorTask`实例（传入驱动对象与配置参数），封装为调度器任务（周期500ms）；  
  4. 初始化调度器（软定时器，调度周期100ms），添加核心任务与维护任务，启动调度并进入无限循环；  
  5. 定义按键中断回调函数，实现任务启停与校准模式切换。

- `drivers/xxx_driver`：硬件驱动模块，均采用“实例化+方法调用”模式，屏蔽底层细节：  
  - `soil_moisture_driver.py`：`SoilMoistureSensor`类通过ADC读取传感器信号，`read_humidity()`返回归一化后的湿度值（0-100%）；  
  - `potentiometer_driver.py`：`Potentiometer`类通过ADC采集滑动变阻器信号，`read_value()`返回阈值（0-100%）；  
  - `ssd1306_driver.py`：`SSD1306OLED`类通过I2C控制显示屏，`display_data()`接收湿度、阈值等参数并显示；  
  - `passive_buzzer_driver.py`：`Buzzer`类通过PWM输出信号，`play_tone(freq, duration)`控制报警声频率与时长；  
  - `piranha_led_driver.py`：`PiranhaLED`类通过PWM控制亮度，支持常亮与闪烁模式。

- `tasks/`：任务逻辑模块：  
  - `sensor_task.py`：`SoilMonitorTask`类关键逻辑：  
    1. `__init__`：初始化硬件实例、滤波缓冲（容量5）、校准参数；  
    2. `tick`：每500ms执行一次，流程为“读取湿度与阈值→均值滤波→阈值对比→控制报警与显示”；  
    3. `calibrate_dry()`/`calibrate_wet()`：分别完成干燥与湿润环境的校准，提升湿度检测精度；  
    4. `pause()`/`resume()`：暂停时关闭报警与LED，恢复时重置滤波缓冲，避免数据异常。  
  - `maintenance.py`：系统维护模块，`task_idle_callback`在调度器空闲时触发GC，`task_err_callback`捕获任务异常并限速打印错误信息。

- `board.py`：板级引脚映射模块，定义`BOARDS`字典（含GraftPort-RP2040的固定引脚、I2C/ADC/PWM接口映射），提供`get_pin`接口，扩展其他开发板时仅需修改该文件。

- `conf.py`：用户配置文件，可自定义参数：`AUTO_START`（任务是否自动启动）、`ENABLE_DEBUG`（调试打印开关）、`GC_THRESHOLD_BYTES`（GC触发阈值）、`ERROR_REPEAT_DELAY_S`（错误打印间隔）等，无配置时使用默认值。

## 软件设计核心思想（Design Idea）
### 1. 分层架构设计：解耦与复用
- 硬件驱动层（drivers/）：仅负责外设底层控制，不包含业务逻辑，如OLED驱动只关心“如何显示数据”，不关心“显示什么数据”；  
- 任务逻辑层（tasks/）：基于驱动层接口实现业务流程，`SoilMonitorTask`调用驱动方法完成监测与反馈，不依赖具体引脚配置；  
- 调度控制层（libs/scheduler.py）：提供通用任务管理能力，支持任务周期调度、暂停/恢复、异常回调，适配多场景需求；  
- 入口层（main.py）：负责“组装”各模块，初始化硬件→创建任务→启动调度，简化系统搭建流程。

### 2. 模块划分原则：高内聚低耦合
- 高内聚：每个模块聚焦单一功能，如`maintenance.py`仅处理系统维护（GC、异常），不参与监测逻辑；  
- 低耦合：模块间通过接口交互，如任务逻辑通过`read_humidity()`获取数据，不直接操作传感器ADC寄存器；  
- 扩展性：新增功能（如远程通知）时，只需在`tasks/`添加新任务，无需修改现有驱动代码。

### 3. 核心机制：保障稳定性与用户体验
- 数据滤波机制：五点均值滤波过滤传感器噪声，避免误报警；  
- 交互反馈机制：按键操作即时响应，校准过程在OLED上提示，提升操作便捷性；  
- 容错机制：传感器初始化重试、硬件操作异常捕获，确保单一模块故障不导致系统崩溃。

## 使用说明（Quick Start）
### 1. 硬件连接
按“硬件要求”中的连线方式，依次连接各模块与主控板，确保供电电压稳定（3.3V）。

### 2. 运行项目（PyCharm + MicroPython插件）
1. 打开PyCharm，安装MicroPython插件并重启；  
2. 插件中选择目标设备为`GraftPort-RP2040`，启用自动检测设备路径；  
3. 将`firmware/`目录设为项目固件目录，修改运行配置：勾选“允许多个实例”，存储为项目文件；  
4. 点击运行按钮上传代码，板载LED闪烁1秒表示启动成功。

## 示例程序（Example）
- 本项目无额外示例代码，可直接修改tasks/sensor_task.py扩展功能（如添加湿度历史记录、自定义报警频率），或修改conf.py调整系统参数。

## 注意事项（Notes）
### 硬件相关：
- 土壤湿度传感器探针需完全插入土壤，避免接触石块等杂物，影响检测精度；
- OLED 显示屏的 I2C 地址若存在冲突，需修改驱动中的地址参数（默认 0x3C）；
- 无源蜂鸣器正负极需正确连接，接反会导致无声。
### 软件相关：
- 必须使用 MicroPython v1.23.0 及以上版本，低版本可能不支持软定时器调度或 ADC 稳定采集；
- 调试打印（ENABLE_DEBUG=True）会占用系统资源，正式使用时建议关闭；
- 校准过程需确保环境稳定（干燥环境可选用干沙，湿润环境可选用饱和水的土壤），否则会导致湿度计算偏差。
## 版本记录（Version History）
v1.0.0：缪贵成完成初始版本，实现核心功能：
- 土壤湿度实时采集与滤波处理；
- 滑动变阻器调节阈值，多方式报警提醒；
- 按键控制任务启停与传感器校准；
- 适配 GraftPort-RP2040 开发板，提供完整驱动与任务代码。

## 联系开发者（Contact）
如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：10696531183@qq.com  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)  

## 许可协议（License）

本项目中，除 `machine` 等 MicroPython 官方模块（MIT 许可证）外，所有由作者编写的驱动与扩展代码均采用 **知识共享署名-非商业性使用 4.0 国际版 (CC BY-NC 4.0)** 许可协议发布。  

您可以自由地：  
- **共享** — 在任何媒介以任何形式复制、发行本作品  
- **演绎** — 修改、转换或以本作品为基础进行创作  

惟须遵守下列条件：  
- **署名** — 您必须给出适当的署名，提供指向本许可协议的链接，同时标明是否（对原始作品）作了修改。您可以用任何合理的方式来署名，但是不得以任何方式暗示许可人为您或您的使用背书。  
- **非商业性使用** — 您不得将本作品用于商业目的。  
- **合理引用方式** — 可在代码注释、文档、演示视频或项目说明中明确来源。  

**版权归 FreakStudio 所有。**
