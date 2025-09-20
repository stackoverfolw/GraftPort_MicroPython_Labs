# Python 文件依赖分析报告
- 根目录：`F:\GraftPort_MicroPython_Labs\proximity_music_light\firmware`  
- 文件数量：**16**  
- 检测到循环依赖：**0**  
- 强制依赖：若 `drivers/__init__.py`、`libs/__init__.py`、`tasks/__init__.py` 存在，则自动设为 `main.py` 的依赖  

---
## 模块依赖表
（`module_id` 使用相对路径作为唯一标识；`dotted_name` 如果为包路径则为点分名）

| Module (module_id) | Dotted name | Size (bytes) | Imports (internal) | Imports (external) | Imported-by |
|---|---:|---:|---|---|---|
| `board` | `board` | 12948 | - | - | `boot`, `main` |
| `boot` | `boot` | 1281 | `board` | `machine.Pin`, `time` | - |
| `conf` | `conf` | 1334 | - | - | `main`, `tasks/maintenance` |
| `drivers/__init__` | `drivers` | 1201 | `drivers/passive_buzzer_driver/__init__`, `drivers/piranha_led_driver/__init__`, `drivers/rcwl9623_driver/__init__` | - | `main` |
| `drivers/passive_buzzer_driver/__init__` | `drivers.passive_buzzer_driver.__init__` | 1113 | `drivers/passive_buzzer_driver/code/buzzer` | - | `drivers/__init__`, `main`, `tasks/sensor_task` |
| `drivers/passive_buzzer_driver/code/buzzer` | `drivers.passive_buzzer_driver.code.buzzer` | 7949 | - | `machine.PWM`, `machine.Pin`, `machine.Timer`, `time` | `drivers/passive_buzzer_driver/__init__` |
| `drivers/piranha_led_driver/__init__` | `drivers.piranha_led_driver.__init__` | 1304 | `drivers/piranha_led_driver/code/piranha_led` | - | `drivers/__init__`, `main` |
| `drivers/piranha_led_driver/code/piranha_led` | `drivers.piranha_led_driver.code.piranha_led` | 8139 | - | `machine.PWM`, `machine.Pin`, `micropython.const` | `drivers/piranha_led_driver/__init__` |
| `drivers/rcwl9623_driver/__init__` | `drivers.rcwl9623_driver.__init__` | 1082 | `drivers/rcwl9623_driver/code/rcwl9623` | - | `drivers/__init__`, `main` |
| `drivers/rcwl9623_driver/code/rcwl9623` | `drivers.rcwl9623_driver.code.rcwl9623` | 25737 | - | `machine.Pin`, `machine.time_pulse_us`, `micropython.const`, `time` | `drivers/rcwl9623_driver/__init__` |
| `libs/__init__` | `libs` | 1025 | `libs/scheduler/__init__` | - | `main` |
| `libs/scheduler/__init__` | `libs.scheduler.__init__` | 1275 | `libs/scheduler/scheduler` | - | `libs/__init__`, `main` |
| `libs/scheduler/scheduler` | `libs.scheduler.scheduler` | 12150 | - | `machine.Timer`, `micropython.const` | `libs/scheduler/__init__` |
| `main` | `main` | 9105 | `board`, `conf`, `drivers/__init__`, `drivers/passive_buzzer_driver/__init__`, `drivers/piranha_led_driver/__init__`, `drivers/rcwl9623_driver/__init__`, `libs/__init__`, `libs/scheduler/__init__`, `tasks/maintenance`, `tasks/sensor_task` | `machine.I2C`, `machine.Pin`, `machine.Timer`, `time` | - |
| `tasks/maintenance` | `tasks.maintenance` | 4047 | `conf` | `conf`, `gc`, `sys`, `time` | `main` |
| `tasks/sensor_task` | `tasks.sensor_task` | 10573 | `drivers/passive_buzzer_driver/__init__` | `collections.deque` | `main` |

---
## 被引用次数排行（Top 20）
| Module | Imported-by count |
|---|---:|
| `drivers/passive_buzzer_driver/__init__` | 3 |
| `board` | 2 |
| `conf` | 2 |
| `drivers/piranha_led_driver/__init__` | 2 |
| `drivers/rcwl9623_driver/__init__` | 2 |
| `libs/scheduler/__init__` | 2 |
| `drivers/__init__` | 1 |
| `drivers/passive_buzzer_driver/code/buzzer` | 1 |
| `drivers/piranha_led_driver/code/piranha_led` | 1 |
| `drivers/rcwl9623_driver/code/rcwl9623` | 1 |
| `libs/__init__` | 1 |
| `libs/scheduler/scheduler` | 1 |
| `tasks/maintenance` | 1 |
| `tasks/sensor_task` | 1 |
| `boot` | 0 |
| `main` | 0 |
