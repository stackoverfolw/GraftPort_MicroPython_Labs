# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2025/10.14 上午11:17
# @Author  : 缪贵成
# @File    : main.py
# @Description : 主程序文件夹，主要用于初始化配置、创建任务和启动任务。
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

# 导入硬件相关模块
from machine import Pin, I2C, Timer, UART

# 导入时间相关模块
import time

# 导入板级支持包
import board
# 导入配置文件
from conf import *
# 导入lib文件夹下面自定义库
from libs.scheduler import Scheduler, Task
# 导入drivers文件夹下面传感器模块驱动库
from drivers.bus_step_motor_driver import BusStepMotor, PCA9685
from drivers.pn532_driver import PN532_UART, PN532

#  导入tasks文件夹下面任务模块
from tasks.maintenance import task_idle_callback, task_err_callback
from tasks.maintenance import GC_THRESHOLD_BYTES, ERROR_REPEAT_DELAY_S
from tasks.sensor_task import NFCDoorTask

# ======================================== 全局变量 ============================================

I2C1_FREQ = 400_000
UART_BAUDRATE = 115200  # PN532 UART通信波特率

# 授权NFC卡UID列表（示例值，需根据实际卡片修改）
AUTHORIZED_UIDS = [
    ['0x86', '0x3e', '0x29', '0x2'],
    ['0x64', '0xb3', '0x7a', '0x5'],
]

# ======================================== 功能函数 ============================================

def fatal_hang(led: Pin, msg: str,
               on_ms: int = 150, off_ms: int = 150,
               pulses: int = 2, pause_s: float = 1.0) -> None:
    """
    在检测到严重错误时阻塞运行：板载 LED 按指定节奏闪烁，并不断在终端打印提示信息。

    Args:
        led (Pin): 已初始化的板载 LED Pin 对象（输出模式）。
        msg (str): 要在终端重复打印的错误/提示信息。
        on_ms (int): 每次闪烁点亮时长，单位毫秒（默认 150ms）。
        off_ms (int): 每次闪烁熄灭时长，单位毫秒（默认 150ms）。
        pulses (int): 每个循环内的闪烁次数（例如 2 表示两短闪）。
        pause_s (float): 每个循环后的静默暂停，单位秒（默认 1.0s）。

    Returns:
        None: 该函数不会返回（无限循环），除非外部抛出 KeyboardInterrupt。
    """
    try:
        # 确保 LED 初始为灭
        try:
            led.value(0)
        except Exception:
            pass

        # 无限循环：每个循环打印并闪烁 pulses 次，然后 pause
        while True:
            for i in range(pulses):
                # 在每次点亮前打印提示（频率可根据需要调整）
                try:
                    print(msg)
                except Exception:
                    # 打印失败也不要中断，至少确保 LED 行为正常
                    pass

                # LED 点亮
                try:
                    led.value(1)
                except Exception:
                    pass
                # 等待点亮时长
                time.sleep_ms(on_ms)

                # LED 熄灭
                try:
                    led.value(0)
                except Exception:
                    pass
                # 等待熄灭时长
                time.sleep_ms(off_ms)

            # 循环间较长暂停
            time.sleep(pause_s)

    except KeyboardInterrupt:
        # 如果在 REPL 手动中断（Ctrl-C）则关闭 LED 并把中断抛出，便于调试
        try:
            led.value(0)
        except Exception:
            pass
        raise
    except Exception as e:
        # 捕获意外异常，打印并灭灯后短暂等待，继续挂起
        try:
            print("fatal_hang internal error:", e)
        except Exception:
            pass
        try:
            led.value(0)
        except Exception:
            pass
        while True:
            time.sleep(1)


def button_handler(pin: Pin) -> None:
    """
    外部中断回调：切换任务运行/暂停状态。

    在外部中断触发时被调用，用于在运行态与暂停态之间切换 `sensor_task`。
        - 当任务正在运行时：调用调度器暂停任务，并**立即**关闭与任务相关的外设（LED / 蜂鸣器）。
        - 当任务已暂停时：调用调度器恢复任务运行。

    Args:
        pin (Pin): 触发中断的输入 Pin 对象（由外部中断注册时指定）。

    Returns:
        None

    Notes:
        - 该函数设计为中断回调（ISR）使用，应尽量保持简短与非阻塞，避免大量内存分配和长时间阻塞操作。
        - 这里包含少量打印（仅在 ENABLE_DEBUG 打开时）与 try/except 捕获，用于兼容调试与保证回调的稳健性。
    """
    global nfc, motor, sensor_task
    if sensor_task._state == Task.TASK_RUN:
        # 暂停任务
        sc.pause(sensor_task)
        if ENABLE_DEBUG:
            print("task_sensor paused")
        # 暂停时立即关闭
        try:
            sensor_task_obj.close_door()
        except Exception:
            pass
    else:
        # 恢复任务
        sc.resume(sensor_task)

        if ENABLE_DEBUG:
            print("task_sensor resumed")


# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 上电延时3s
time.sleep(3)
# 打印调试信息
print("FreakStudio : NFC Authorized Stepper Motor Simulation Access Control System")

# 获取板载LED的固定引脚
led_pin = board.get_fixed_pin("LED")
led = Pin(led_pin, Pin.OUT)

# 获取板载按键的固定引脚
button_pin = board.get_fixed_pin("BUTTON")
# 创建板载按键实例
button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
button.irq(trigger=Pin.IRQ_FALLING, handler=button_handler)

# I2C1: PCA9685（必须）
i2c1_sda_pin, i2c1_scl_pin = board.get_i2c_pins(1)
i2c1 = I2C(1, scl=i2c1_scl_pin, sda=i2c1_sda_pin, freq=I2C1_FREQ)
try:
    addrs1 = i2c1.scan()
    if ENABLE_DEBUG:
        print("I2C1 scan result (hex):", [hex(a) for a in addrs1])
except Exception as e_scan1:
    fatal_hang(led, f"[FATAL] I2C1 scan failed: {e_scan1}")
    addrs1 = []
# ---------- PCA9685 初始化（必须，地址范围 0x3F~0x41） ----------
pca_addr = None
for addr in addrs1:
    if 0x3F <= addr <= 0x41:
        pca_addr = addr
        break

if pca_addr is None:
    # 没找到设备，直接报错退出
    fatal_hang(led, f"[FATAL] PCA9685 not found on I2C1. I2C1 devices: {[hex(a) for a in addrs1]}")
else:
    # 找到设备，尝试初始化并捕获异常
    try:
        pca9685 = PCA9685(i2c1)
        if ENABLE_DEBUG:
            print(f"PCA9685 initialized at {hex(pca_addr)}")
        motor = BusStepMotor(pca9685, 1)
    except Exception as e_pca:
        fatal_hang(led, f"[FATAL] PCA9685 init failed: {e_pca}")

# 初始化NFC
# 获取UART引脚
uart_tx_pin, uart_rx_pin = board.get_uart_pins(1)
try:
    uart = UART(1, UART_BAUDRATE, tx=uart_tx_pin, rx=uart_rx_pin, timeout=100)
    # 初始化PN532模块
    nfc = PN532_UART(uart)
    # 验证PN532连接
    if nfc.firmware_version:
        if ENABLE_DEBUG:
            print("PN532 NFC success to initialized")
    else:
        fatal_hang(led, "[FATAL] don't connect to PN532")
except Exception as e_uart:
    fatal_hang(led, f"[FATAL] UART/PN532 failed to initialized: {e_uart}")

# 输出调试消息
print("All peripherals initialized.")

# 打印维护任务相关的代码常量
print("GC threshold:", GC_THRESHOLD_BYTES)
print("Error repeat delay:", ERROR_REPEAT_DELAY_S)

# 创建传感器任务实例
sensor_task_obj = NFCDoorTask(pn532=nfc, motor=motor, oled=None, authorized_uids=AUTHORIZED_UIDS, enable_debug=True)
sensor_task = Task(sensor_task_obj.tick, interval=200, state=Task.TASK_RUN)

# 创建任务调度器,定时周期为50ms
sc = Scheduler(Timer(-1), interval=50, task_idle=task_idle_callback, task_err=task_err_callback)

# 添加任务
sc.add(sensor_task)

# 根据 AUTO_START 决定是否立即运行
if not AUTO_START:
    sc.pause(sensor_task)

# ========================================  主程序  ===========================================

# 开启调度
sc.scheduler()


