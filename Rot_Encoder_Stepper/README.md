# 步进电机与编码器交互控制系统

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
传统步进电机控制系统多依赖固定程序或单一输入设备，存在调节灵活性差、状态反馈不直观等问题，难以满足精密控制场景需求。本项目基于GraftPort-RP2040开发板，整合EC11旋转编码器（参数调节）、步进电机（执行机构）与OLED屏幕（状态显示），通过MicroPython实现“编码器输入-电机控制-可视化反馈”的闭环系统，解决传统方案中交互性与可控性不足的痛点。

### 项目主要功能概览
本项目基于MicroPython开发，核心功能是通过EC11旋转编码器采集用户输入（旋转调节参数、按压确认），经处理后控制步进电机按设定参数（速度、角度）运行；同时在OLED屏幕上实时显示电机状态（当前角度、运行速度、是否暂停），支持板载按键触发任务暂停/恢复，内置错误处理与自动内存管理，适配小型精密设备（如3D打印机喷头、机械臂关节）的控制场景。

### 适用场景或应用领域
- 精密机械控制：如小型数控机床的进给调节、3D打印机的挤出机控制；  
- 智能家居设备：窗帘电机的行程调节、阀门的开度控制；  
- 教学实训：用于嵌入式课程中“编码器交互、步进电机驱动、I2C通信”等知识点的实践；  
- 创客项目：作为轻量化运动控制模块，快速集成到DIY机械装置中。


## 主要功能（Features）
- **编码器精准交互**：EC11旋转编码器支持旋转计数（每步1脉冲）与按压触发，内置10ms防抖处理，旋转调节电机参数（速度/角度），按压确认执行，响应灵敏无卡顿；  
- **步进电机精密控制**：基于PCA9685驱动板控制步进电机，支持角度（0-360°）与速度（50-500ms/圈）自定义，正反转切换，角度控制误差≤1°；  
- **可视化状态反馈**：SSD1306 OLED屏幕实时显示电机当前角度、设定速度、运行状态（运行/暂停）及编码器调节值，信息直观易懂；  
- **任务中断控制**：板载按键触发下降沿中断，短按切换电机任务“运行/暂停”，暂停时电机保持当前位置，恢复后继续执行；  
- **自动内存管理**：系统空闲时自动触发垃圾回收（GC），避免内存碎片导致运行异常，可通过`conf.py`配置GC触发阈值；  
- **多板级适配**：通过`board.py`定义引脚映射，默认适配GraftPort-RP2040，扩展其他RP2040板型仅需添加配置，无需修改核心逻辑。


## 硬件要求（Hardware Requirements）
项目基于GraftPort-RP2040开发板作为主控：

**所需模块清单**：  
- 执行模块：42步进电机 + PCA9685 PWM驱动板（I2C通信，地址0x40）；  
- 交互模块：EC11旋转编码器（含按压按键，3Pin信号输出）；  
- 显示模块：SSD1306 OLED屏幕（I2C通信，128x64分辨率，地址0x3C）；  
- 控制模块：板载按键（1路，用于任务暂停/恢复）、板载LED（1路，状态指示）；  
- 供电模块：SY7656锂电池充放电模块（输出3.3V，为主控及模块供电）。  

**连接方式**：  
1. PCA9685驱动板：VCC接3.3V、GND接GND、SDA接I2C1-SDA引脚、SCL接I2C1-SCL引脚；  
2. 步进电机：A+、A-、B+、B-对应连接PCA9685的CH0-CH3通道；  
3. EC11编码器：VCC接3.3V、GND接GND、DT接GPIO引脚、CLK接GPIO引脚、SW（按键）接GPIO引脚；  
4. OLED屏幕：VCC接3.3V、GND接GND、SDA接I2C0-SDA引脚、SCL接I2C0-SCL引脚；  
5. 板载按键：默认使用开发板固定引脚（上拉输入，另一端接GND）。  


## 软件环境（Software Environment）
- 核心固件：MicroPython v1.23.0（需适配GraftPort-RP2040，支持`machine.I2C/Pin/Timer/ADC`模块）；  
- 开发IDE：PyCharm（安装MicroPython插件，支持代码上传、REPL调试交互）；  
- 辅助工具：  
  - mpremote v0.11.0+（用于命令行式文件传输与设备交互）；  
  - Python 3.10+（运行本地辅助脚本，如参数校准工具）；  
- 依赖模块：无第三方库，所有驱动（PCA9685、EC11、SSD1306等）均为项目自定义实现。  


## 文件结构（File Structure）
```
firmware/
├── board.py               # 板级支持文件，定义 GraftPort-RP2040 的引脚映射
├── conf.py                # 配置文件，存放可自定义参数（调试开关、GC 阈值等）
├── main.py                # 项目入口文件，负责硬件初始化、任务创建与调度启动
├── boot.py                # 启动脚本，初始化板载 LED，提示系统启动状态
├── drivers/               # 硬件驱动文件夹，封装各外设的控制接口
│   ├── __init__.py         # 驱动包导出，简化外部调用
│   ├── bus_step_motor_driver/  # 步进电机驱动，含 PCA9685 与 BusStepMotor 类
│   ├── rotaryencoder_driver/   # EC11 编码器驱动，提供旋转计数与按键检测
│   └── ssd1306_driver/         # SSD1306 OLED 驱动，提供数据显示方法
├── libs/                  # 通用工具库文件夹
│   ├── __init__.py         # 库包导出
│   └── scheduler.py        # 任务调度器库，实现多任务周期管理、空闲 / 异常回调
└── tasks/                 # 任务逻辑文件夹，与硬件驱动解耦
    ├── __init__.py         # 任务包导出
    └── motor_task.py       # 核心任务模块，定义 MotorControlTask 类，实现控制逻辑
```

## 文件说明（File Description）

### 1. 启动与入口模块
- `boot.py`：系统启动脚本，上电后初始化板载LED，点亮1秒后熄灭，提示硬件启动完成；  
- `main.py`：项目核心入口，逻辑包括：  
  1. 延时2秒等待硬件稳定，通过`board.py`获取各模块引脚配置；  
  2. 初始化I2C总线（I2C0用于OLED，I2C1用于PCA9685）、编码器、按键、LED等硬件；  
  3. 创建`MotorControlTask`实例（传入驱动对象与配置参数），封装为调度任务（周期50ms）；  
  4. 初始化调度器（软定时器，周期10ms），添加核心任务与GC维护任务；  
  5. 注册按键中断回调，实现任务暂停/恢复控制，启动调度器进入循环。  


### 2. 硬件驱动
#### 步进电机驱动（bus_step_motor_driver/）
- **核心类**：  
  - `PCA9685(i2c, addr=0x40)`：初始化PWM驱动板，提供`set_pwm(channel, on, off)`方法控制输出；  
  - `BusStepMotor(pca, channels)`：绑定电机与驱动通道，关键方法：  
    - `set_speed(speed_ms)`：设置转速（单位：ms/圈，范围50-500）；  
    - `rotate(angle)`：旋转指定角度（正角顺时针，负角逆时针）；  
    - `stop()`：立即停止电机运行，保持当前位置。  


#### 旋转编码器驱动（rotaryencoder_driver/）
- **核心类**：`RotaryEncoder(dt_pin, clk_pin, sw_pin)`  
- **关键方法**：  
  - `get_count()`：返回旋转计数（正转递增，反转递减）；  
  - `is_pressed()`：返回按键是否被按下（已过防抖处理）；  
  - `reset_count()`：重置旋转计数为0，用于参数调节复位。  


#### OLED驱动（ssd1306_driver/）
- **核心类**：`SSD1306OLED(i2c, addr=0x3C)`  
- **关键方法**：  
  - `init()`：初始化屏幕，清屏并设置显示方向；  
  - `display_motor_status(angle, speed, is_running)`：显示电机当前角度、速度及运行状态；  
  - `display_menu(param_name, value)`：显示参数调节菜单（如“Speed: 200ms”）。  


### 3. 任务逻辑（motor_task.py）
- **核心类**：`MotorControlTask`，实现“编码器输入-电机控制-显示反馈”闭环逻辑：  
  - `__init__`：初始化硬件实例、参数缓存（目标角度、速度）、状态标记（`is_running`）；  
  - `tick`：每50ms执行一次，流程为“读取编码器输入→更新参数→控制电机运行→刷新OLED显示”；  
  - `_handle_encoder`：处理旋转输入（调节速度/角度）和按压确认（执行旋转）；  
  - `toggle_pause`：切换任务运行/暂停状态，暂停时电机停转，OLED显示“PAUSED”。  


### 4. 配置与工具
- `board.py`：定义`BOARDS`字典，包含GraftPort-RP2040的I2C、编码器、按键等引脚映射，提供`get_pin`接口；  
- `conf.py`：可配置参数，如`ENABLE_DEBUG`（调试打印）、`GC_THRESHOLD_BYTES`（GC触发阈值）、`MOTOR_DEFAULT_SPEED`（默认转速）；  
- `libs/scheduler.py`：提供`Scheduler`类，支持任务添加、周期调度、异常回调，确保多任务有序执行。  


## 软件设计核心思想（Design Idea）
### 1. 分层架构设计
- **驱动层（drivers/）**：专注硬件底层控制，与业务逻辑解耦（如步进电机驱动只关心“如何转”，不关心“转多少”）；  
- **任务层（tasks/）**：基于驱动接口实现业务流程，`MotorControlTask`封装“输入-处理-输出”逻辑，不依赖具体引脚；  
- **调度层（libs/scheduler.py）**：提供通用任务管理，支持多任务并行、优先级调度，适配复杂场景扩展；  
- **配置层（board.py/conf.py）**：抽象硬件差异与运行参数，使核心代码可跨板复用、参数可灵活调整。  


### 2. 状态机管理
- 系统定义3种核心状态：`IDLE`（空闲，等待参数调节）、`RUNNING`（运行，执行电机旋转）、`PAUSED`（暂停，保持当前状态）；  
- 状态转换通过事件触发（编码器按压→从IDLE到RUNNING，按键短按→在RUNNING与PAUSED间切换），逻辑清晰可追溯。  


### 3. 交互反馈机制
- 实时性：编码器输入每10ms检测一次，电机状态每50ms更新一次，OLED显示同步刷新，确保交互无延迟；  
- 直观性：通过屏幕菜单区分参数调节与运行状态，旋转时数值实时变化，按压后明确提示“执行中”，用户操作有明确反馈。  


## 使用说明（Quick Start）
### 1. 硬件连接
按“硬件要求”中的连接方式，将步进电机、编码器、OLED等模块与GraftPort-RP2040连接，确保供电稳定（3.3V）。

### 2. 配置参数（可选）
修改`conf.py`调整系统参数：
```python
ENABLE_DEBUG = True          # 开启调试打印，查看实时数据
GC_THRESHOLD_BYTES = 100000  # 内存低于100KB时触发GC
MOTOR_DEFAULT_SPEED = 200    # 电机默认转速（200ms/圈）
```

示例程序（Example）
- 本项目无其他示例
## 注意事项（Notes）
### 硬件相关：
- 步进电机与 PCA9685 的接线需对应 A、B 相，接反会导致旋转方向错误或卡顿；
- 编码器的 DT/CLK 引脚需接带内部上拉的 GPIO，否则可能出现误触发；
- OLED 屏幕若地址冲突（默认 0x3C），需修改驱动中的DEFAULT_ADDR参数。
### 软件相关：
- 电机转速不宜设置过低（<50ms / 圈），可能导致扭矩不足；过高（>500ms / 圈）会影响响应速度；
- 调试模式（ENABLE_DEBUG=True）会占用系统资源，正式使用时建议关闭；
- 更换开发板后，需在board.py中添加对应板型的引脚配置，并调用set_active_board()激活。
## 版本记录（Version History）
v1.0.0：缪贵成完成初始版本
- 实现 EC11 编码器参数调节与确认功能；
- 支持步进电机速度 / 角度控制及正反转；
- 适配 OLED 屏幕状态显示与板载按键暂停 / 恢复；
- 集成任务调度与自动 GC，确保系统稳定运行。
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
