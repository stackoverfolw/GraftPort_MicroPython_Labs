# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/9/9 下午11:17   
# @Author  : 李清水            
# @File    : main.py       
# @Description : 主程序文件夹，主要用于初始化配置、创建任务和启动任务。
# @License : CC BY-NC 4.0

# ======================================== 导入相关模块 =========================================

# 导入硬件相关模块
from machine import Pin, I2C, Timer, ADC
# 导入时间相关模块
import time

# 导入板级支持包
import board
# 导入配置文件
from conf import *
# 导入lib文件夹下面自定义库
from libs.scheduler import Scheduler, Task
# 导入drivers文件夹下面传感器模块驱动库
from drivers.bus_dc_motor_driver import PCA9685, BusDCMotor
from drivers.potentiometer_driver import Potentiometer
from drivers.ssd1306_driver import SSD1306_I2C
#  导入tasks文件夹下面任务模块
from tasks.maintenance import task_idle_callback, task_err_callback
from tasks.maintenance import GC_THRESHOLD_BYTES, ERROR_REPEAT_DELAY_S
from tasks.sensor_task import SensorPotMotorTask

# ======================================== 全局变量 ============================================

I2C0_FREQ = 400_000
I2C1_FREQ = 100_000
oled = None
motor = None
pot = None
last_err = None

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
    外部中断回调：按键按下时切换 MotorControlTask 的运行/暂停状态。

    - 当任务正在运行时：暂停任务并立即停转电机。
    - 当任务已暂停时：恢复任务运行。

    Args:
        pin (Pin): 触发中断的输入 Pin 对象（由外部中断注册时指定）。

    Notes:
        - 该函数设计为中断回调（ISR）使用，应保持简短和非阻塞。
        - 可打印调试信息，便于确认任务状态。
    """
    global motor_task, motor, led, sc

    if motor_task._state == Task.TASK_RUN:
        # 暂停任务
        sc.pause(motor_task)
        if ENABLE_DEBUG:
            print("motor_task paused")
        # 暂停时立即停电机
        try:
            motor.stop_motor(1)
        except Exception:
            pass
        # 可选：LED亮表示暂停
        try:
            led.value(1)
        except Exception:
            pass
    else:
        # 恢复任务
        sc.resume(motor_task)
        if ENABLE_DEBUG:
            print("motor_task resumed")
        # LED灭表示运行
        try:
            led.value(0)
        except Exception:
            pass

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================


time.sleep(3)
print("Initializing hardware...")

# 板载LED
led_pin = board.get_fixed_pin("LED")
led = Pin(led_pin, Pin.OUT)

# 获取板载按键的固定引脚
button_pin = board.get_fixed_pin("BUTTON")
# 创建板载按键实例
button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
button.irq(trigger=Pin.IRQ_FALLING, handler=button_handler)

# ---------- I2C 初始化 ----------

# I2C0: OLED（可选）
i2c0_sda_pin, i2c0_scl_pin = board.get_i2c_pins(0)
i2c0 = I2C(0, scl=i2c0_scl_pin, sda=i2c0_sda_pin, freq=I2C0_FREQ)

# I2C1: PCA9685（必须）
i2c1_sda_pin, i2c1_scl_pin = board.get_i2c_pins(1)
i2c1 = I2C(1, scl=i2c1_scl_pin, sda=i2c1_sda_pin, freq=I2C1_FREQ)

# ---------- 扫描总线 ----------
try:
    addrs0 = i2c0.scan()
    if ENABLE_DEBUG:
        print("I2C0 scan result (hex):", [hex(a) for a in addrs0])
except Exception as e_scan0:
    fatal_hang(led, f"[FATAL] I2C0 scan failed: {e_scan0}")
    addrs0 = []

try:
    addrs1 = i2c1.scan()
    if ENABLE_DEBUG:
        print("I2C1 scan result (hex):", [hex(a) for a in addrs1])
except Exception as e_scan1:
    fatal_hang(led, f"[FATAL] I2C1 scan failed: {e_scan1}")
    addrs1 = []

# ---------- OLED 初始化（可选，地址范围 0x3A~0x3E） ----------
oled = None
OLED_ADDRESS = None
for addr in addrs0:
    if 0x3A <= addr <= 0x3E:
        OLED_ADDRESS = addr
        break

if OLED_ADDRESS is not None:
    try:
        oled = SSD1306_I2C(i2c0, OLED_ADDRESS, 128, 64, False)
        if ENABLE_DEBUG:
            print(f"OLED initialized at {hex(OLED_ADDRESS)} on I2C0")
    except Exception as e_oled:
        print(f"[WARNING] OLED init failed: {e_oled}")
        oled = None
else:
    if ENABLE_DEBUG:
        print("[INFO] OLED not detected on I2C0, skipping initialization.")

# ---------- PCA9685 初始化（必须，地址范围 0x3F~0x41） ----------
pca_addr = None
for addr in addrs1:
    if 0x3F <= addr <= 0x48:
        pca_addr = addr
        break

if pca_addr is None:
    fatal_hang(led, f"[FATAL] PCA9685 not found on I2C1 within address range 0x3F~0x41. I2C1 devices: {[hex(a) for a in addrs1]}")

try:
    pwm_driver = PCA9685(i2c1, pca_addr)  # 如果构造函数只需要 I2C 对象
    if ENABLE_DEBUG:
        print(f"PCA9685 initialized at {hex(pca_addr)} on I2C1")
    motor = BusDCMotor(pwm_driver, 1)  # 使用通道1
except Exception as e_pca:
    fatal_hang(led, f"[FATAL] PCA9685 init failed: {e_pca}")

# 初始化滑动变阻器
adc_pin = board.get_adc_pins(0)[0]
adc_pin = Pin(adc_pin, Pin.IN)  # 配置引脚为输入
adc = ADC(adc_pin)  # 假设ADC0
pot = Potentiometer(adc=adc, vref=3.3)


motor_task_obj = SensorPotMotorTask(speed_exp=3.0, poten=pot, motor=motor, oled=oled, enable_debug=False)
motor_task = Task(motor_task_obj.tick, interval=100, state=Task.TASK_RUN)

# 创建任务调度器
sc = Scheduler(Timer(-1), interval=100, task_idle=task_idle_callback, task_err=task_err_callback)
sc.add(motor_task)

if not AUTO_START:
    sc.pause(motor_task)

# ======================================== 主程序 ============================================

sc.scheduler()
